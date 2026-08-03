"""
Pipeline Manager and Scheduler.
Handles pipeline execution (Receita -> Postgres -> Oracle) and background periodic checks.
"""

import asyncio
import logging
import sys
import threading
import time
from typing import Dict, List, Optional
from apscheduler.schedulers.background import BackgroundScheduler

from config import Config, config
from database import Database
from downloader import Downloader
from oracle_migrator import OracleMigrator
from processor import get_file_type, process_file

logger = logging.getLogger(__name__)

PROCESSING_ORDER = [
    "CNAECSV",  # cnaes
    "MOTICSV",  # motivos
    "MUNICCSV",  # municipios
    "NATJUCSV",  # naturezas_juridicas
    "PAISCSV",  # paises
    "QUALSCSV",  # qualificacoes_socios
    "EMPRECSV",  # empresas
    "ESTABELE",  # estabelecimentos
    "SOCIOCSV",  # socios
    "SIMPLESCSV",  # dados_simples
]

# Map file type to PG table name
FILE_TYPE_TO_TABLE = {
    "CNAECSV": "cnaes",
    "MOTICSV": "motivos",
    "MUNICCSV": "municipios",
    "NATJUCSV": "naturezas_juridicas",
    "PAISCSV": "paises",
    "QUALSCSV": "qualificacoes_socios",
    "EMPRECSV": "empresas",
    "ESTABELE": "estabelecimentos",
    "SOCIOCSV": "socios",
    "SIMPLESCSV": "dados_simples",
}


def get_file_priority(filename: str) -> int:
    """Get processing priority for a file."""
    file_type = get_file_type(filename)
    if file_type in PROCESSING_ORDER:
        return PROCESSING_ORDER.index(file_type)
    return 999


class PipelineManager:
    """Stateful Manager to execute pipeline jobs and report real-time status."""

    def __init__(self, cfg: Config = config):
        self.config = cfg
        self.status = {
            "state": "IDLE",  # IDLE, DOWNLOADING, PROCESSING_PG, MIGRATING_ORACLE, COMPLETED, ERROR
            "current_month": None,
            "current_file": None,
            "files_total": 0,
            "files_processed": 0,
            "current_rows": 0,
            "oracle_rows": 0,
            "oracle_current_table": None,
            "error": None,
            "last_run": None,
        }
        self.log_listeners: List[asyncio.Queue] = []
        self._lock = threading.Lock()

    def log(self, message: str, level: str = "INFO"):
        """Emit log message to listeners and standard logger."""
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        formatted = f"[{timestamp}] [{level}] {message}"
        if level == "ERROR":
            logger.error(message)
        else:
            logger.info(message)

        # Notify websockets / queues
        for queue in self.log_listeners:
            try:
                queue.put_nowait({"type": "log", "message": formatted})
            except Exception:
                pass

    def update_status(self, **kwargs):
        """Update current status state dictionary."""
        with self._lock:
            self.status.update(kwargs)
            state_payload = {"type": "status", "data": dict(self.status)}

        for queue in self.log_listeners:
            try:
                queue.put_nowait(state_payload)
            except Exception:
                pass

    def run_pipeline(self, target_month: Optional[str] = None, force: bool = False):
        """Execute full pipeline workflow in background thread."""
        thread = threading.Thread(
            target=self._execute_pipeline, args=(target_month, force), daemon=True
        )
        thread.start()

    def _execute_pipeline(self, target_month: Optional[str], force: bool):
        """Internal execution method."""
        downloader = Downloader(self.config)

        try:
            # 1. Resolve month
            self.update_status(state="CHECKING", error=None)
            available = downloader.get_available_directories()
            if target_month:
                if target_month not in available:
                    raise ValueError(f"Mês {target_month} não encontrado na Receita. Disponíveis: {available}")
                directory = target_month
            else:
                directory = downloader.get_latest_directory()

            self.log(f"Iniciando pipeline para o mês: {directory}")
            self.update_status(current_month=directory)

            db = Database(self.config.database_url)

            if force:
                self.log(f"Modo força ativado. Limpando registros anteriores de {directory}")
                db.clear_processed_files(directory)

            all_files = downloader.get_directory_files(directory)
            processed_pg = db.get_processed_files(directory)
            pending_files = [f for f in all_files if f not in processed_pg]

            # Build initial per-file status dictionary
            file_statuses = {}
            for filename in all_files:
                file_type_raw = get_file_type(filename)
                table_label = FILE_TYPE_TO_TABLE.get(file_type_raw, file_type_raw)
                file_statuses[filename] = {
                    "filename": filename,
                    "file_type": table_label,
                    "status": "COMPLETED" if filename in processed_pg else "PENDING",
                    "rows": 0,
                    "error": None,
                }

            self.update_status(
                current_month=directory,
                files_total=len(all_files),
                file_statuses=file_statuses,
            )

            # 2. Process Postgres Staging
            if pending_files:
                self.log(f"Falta processar {len(pending_files)} arquivos no PostgreSQL staging...")
                pending_files.sort(key=get_file_priority)

                self.update_status(
                    state="DOWNLOADING",
                    files_processed=len(all_files) - len(pending_files),
                )

                def on_download_progress(fname, downloaded, total, pct):
                    info = file_statuses.get(fname)
                    if info:
                        info["download_pct"] = pct
                        info["downloaded_bytes"] = downloaded
                        info["total_bytes"] = total
                        if info["status"] not in ["PROCESSING_PG", "COMPLETED", "ERROR"]:
                            info["status"] = "DOWNLOADING"
                        self.update_status(file_statuses=file_statuses)

                file_iterator = downloader.download_files(
                    directory, pending_files, progress_callback=on_download_progress
                )
                for idx, (csv_path, zip_filename) in enumerate(file_iterator, 1):
                    file_info = file_statuses.get(zip_filename, {})
                    file_info["status"] = "PROCESSING_PG"
                    file_info["download_pct"] = 100.0

                    self.update_status(
                        state="PROCESSING_PG",
                        current_file=zip_filename,
                        files_processed=(len(all_files) - len(pending_files)) + idx - 1,
                        file_statuses=file_statuses,
                    )
                    self.log(f"Lendo e inserindo no PostgreSQL: {zip_filename}")

                    try:
                        rows_file = 0
                        for batch, table_name, columns in process_file(csv_path, self.config.batch_size):
                            db.bulk_upsert(batch, table_name, columns)
                            rows_file += len(batch)
                            file_info["rows"] = rows_file
                            self.update_status(current_rows=rows_file, file_statuses=file_statuses)

                        db.mark_processed(directory, zip_filename)
                        file_info["status"] = "COMPLETED"
                        self.log(f"Concluído PG {zip_filename}: {rows_file:,} registros.")
                    except Exception as file_err:
                        file_info["status"] = "ERROR"
                        file_info["error"] = str(file_err)
                        self.log(f"Erro ao processar arquivo {zip_filename}: {file_err}", level="ERROR")
                    finally:
                        self.update_status(file_statuses=file_statuses)
                        if csv_path.exists() and not self.config.keep_files:
                            csv_path.unlink()

                self.update_status(files_processed=len(all_files))
            else:
                self.log("Todos os arquivos já estão carregados no PostgreSQL staging.")

            # 3. Process Oracle Migration
            if self.config.enable_oracle:
                self.log("Iniciando migração para o Oracle DB...")
                self.update_status(state="MIGRATING_ORACLE", oracle_rows=0)

                oracle_migrator = OracleMigrator(self.config)
                oracle_migrator.ensure_oracle_tables()

                # Determine PG tables to stream
                db.connect()
                for file_type in PROCESSING_ORDER:
                    pg_table = FILE_TYPE_TO_TABLE.get(file_type)
                    if not pg_table:
                        continue

                    self.update_status(oracle_current_table=pg_table)
                    self.log(f"Migrando tabela {pg_table} do PostgreSQL para o Oracle ({oracle_migrator.get_oracle_table_name(pg_table)})...")

                    def on_oracle_progress(total_migrated, table_name):
                        self.update_status(oracle_rows=total_migrated)

                    migrated = oracle_migrator.migrate_table_data(
                        db.conn,
                        pg_table,
                        directory,
                        progress_callback=on_oracle_progress,
                    )
                    self.log(f"Tabela {pg_table} migrada com sucesso: {migrated:,} linhas.")

                oracle_migrator.disconnect_oracle()

            self.log(f"Pipeline do mês {directory} finalizado com sucesso!")
            self.update_status(
                state="COMPLETED",
                current_file=None,
                oracle_current_table=None,
                last_run=time.strftime("%Y-%m-%d %H:%M:%S"),
            )

        except Exception as e:
            self.log(f"Erro durante a execução do pipeline: {e}", level="ERROR")
            self.update_status(state="ERROR", error=str(e))

        finally:
            try:
                downloader.cleanup()
            except Exception:
                pass


pipeline_manager = PipelineManager(config)

scheduler = BackgroundScheduler()


def init_scheduler():
    """Start background scheduler for monthly automatic pipeline runs."""

    def scheduled_job():
        logger.info("Scheduler disparado: checando novos arquivos da Receita...")
        pipeline_manager.run_pipeline()

    # Parse cron expression (e.g. '0 3 1 * *')
    cron_parts = config.cron_schedule.split()
    if len(cron_parts) == 5:
        minute, hour, day, month, day_of_week = cron_parts
        scheduler.add_job(
            scheduled_job,
            "cron",
            minute=minute,
            hour=hour,
            day=day,
            month=month,
            day_of_week=day_of_week,
            id="monthly_cnpj_job",
            replace_existing=True,
        )
        scheduler.start()
        logger.info(f"Background Scheduler iniciado com a regra cron: {config.cron_schedule}")
