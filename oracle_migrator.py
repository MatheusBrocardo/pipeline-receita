"""
Oracle DB Migration Module for CNPJ Data Pipeline.
Migrates data from PostgreSQL staging tables to Oracle DB using python-oracledb in Thin Mode.
"""

import gc
import logging
import time
from typing import Callable, Dict, Optional
import oracledb
import os
from config import Config

logger = logging.getLogger(__name__)


oracle_home = os.environ.get("ORACLE_HOME")
if oracle_home:
    try:
        oracledb.init_oracle_client(lib_dir=oracle_home)
    except Exception as _e:
        logger.debug(f"init_oracle_client exception: {_e}")

# Map table columns and primary keys for Oracle DDL & MERGE statements
TABLE_SCHEMAS: Dict[str, Dict] = {
    "cnaes": {
        "columns": ["codigo", "descricao"],
        "pk": ["codigo"],
        "oracle_types": {
            "codigo": "VARCHAR2(7)",
            "descricao": "CLOB",
        },
    },
    "motivos": {
        "columns": ["codigo", "descricao"],
        "pk": ["codigo"],
        "oracle_types": {
            "codigo": "VARCHAR2(2)",
            "descricao": "CLOB",
        },
    },
    "municipios": {
        "columns": ["codigo", "descricao"],
        "pk": ["codigo"],
        "oracle_types": {
            "codigo": "VARCHAR2(7)",
            "descricao": "CLOB",
        },
    },
    "naturezas_juridicas": {
        "columns": ["codigo", "descricao"],
        "pk": ["codigo"],
        "oracle_types": {
            "codigo": "VARCHAR2(4)",
            "descricao": "CLOB",
        },
    },
    "paises": {
        "columns": ["codigo", "descricao"],
        "pk": ["codigo"],
        "oracle_types": {
            "codigo": "VARCHAR2(3)",
            "descricao": "CLOB",
        },
    },
    "qualificacoes_socios": {
        "columns": ["codigo", "descricao"],
        "pk": ["codigo"],
        "oracle_types": {
            "codigo": "VARCHAR2(2)",
            "descricao": "CLOB",
        },
    },
    "empresas": {
        "columns": [
            "cnpj_basico",
            "razao_social",
            "natureza_juridica",
            "qualificacao_responsavel",
            "capital_social",
            "porte",
            "ente_federativo_responsavel",
        ],
        "pk": ["cnpj_basico"],
        "oracle_types": {
            "cnpj_basico": "VARCHAR2(8)",
            "razao_social": "VARCHAR2(500)",
            "natureza_juridica": "VARCHAR2(4)",
            "qualificacao_responsavel": "VARCHAR2(2)",
            "capital_social": "NUMBER(18,2)",
            "porte": "VARCHAR2(2)",
            "ente_federativo_responsavel": "VARCHAR2(500)",
        },
    },
    "estabelecimentos": {
        "columns": [
            "cnpj_basico",
            "cnpj_ordem",
            "cnpj_dv",
            "identificador_matriz_filial",
            "nome_fantasia",
            "situacao_cadastral",
            "data_situacao_cadastral",
            "motivo_situacao_cadastral",
            "nome_cidade_exterior",
            "pais",
            "data_inicio_atividade",
            "cnae_fiscal_principal",
            "cnae_fiscal_secundaria",
            "tipo_logradouro",
            "logradouro",
            "numero",
            "complemento",
            "bairro",
            "cep",
            "uf",
            "municipio",
            "ddd_1",
            "telefone_1",
            "ddd_2",
            "telefone_2",
            "ddd_fax",
            "fax",
            "correio_eletronico",
            "situacao_especial",
            "data_situacao_especial",
        ],
        "pk": ["cnpj_basico", "cnpj_ordem", "cnpj_dv"],
        "oracle_types": {
            "cnpj_basico": "VARCHAR2(8)",
            "cnpj_ordem": "VARCHAR2(4)",
            "cnpj_dv": "VARCHAR2(2)",
            "identificador_matriz_filial": "NUMBER(10)",
            "nome_fantasia": "VARCHAR2(500)",
            "situacao_cadastral": "VARCHAR2(2)",
            "data_situacao_cadastral": "DATE",
            "motivo_situacao_cadastral": "VARCHAR2(2)",
            "nome_cidade_exterior": "VARCHAR2(500)",
            "pais": "VARCHAR2(3)",
            "data_inicio_atividade": "DATE",
            "cnae_fiscal_principal": "VARCHAR2(7)",
            "cnae_fiscal_secundaria": "CLOB",
            "tipo_logradouro": "VARCHAR2(100)",
            "logradouro": "VARCHAR2(500)",
            "numero": "VARCHAR2(50)",
            "complemento": "VARCHAR2(500)",
            "bairro": "VARCHAR2(200)",
            "cep": "VARCHAR2(8)",
            "uf": "VARCHAR2(2)",
            "municipio": "VARCHAR2(7)",
            "ddd_1": "VARCHAR2(4)",
            "telefone_1": "VARCHAR2(8)",
            "ddd_2": "VARCHAR2(4)",
            "telefone_2": "VARCHAR2(8)",
            "ddd_fax": "VARCHAR2(4)",
            "fax": "VARCHAR2(8)",
            "correio_eletronico": "VARCHAR2(255)",
            "situacao_especial": "VARCHAR2(500)",
            "data_situacao_especial": "DATE",
        },
    },
    "socios": {
        "columns": [
            "cnpj_basico",
            "identificador_de_socio",
            "nome_socio",
            "cnpj_cpf_do_socio",
            "qualificacao_do_socio",
            "data_entrada_sociedade",
            "pais",
            "representante_legal",
            "nome_do_representante",
            "qualificacao_do_representante_legal",
            "faixa_etaria",
        ],
        "pk": ["cnpj_basico", "identificador_de_socio", "cnpj_cpf_do_socio"],
        "column_map": {
            "qualificacao_do_representante_legal": "quali_do_rep_legal"
        },
        "oracle_types": {
            "cnpj_basico": "VARCHAR2(500)",
            "identificador_de_socio": "VARCHAR2(500)",
            "nome_socio": "VARCHAR2(500)",
            "cnpj_cpf_do_socio": "VARCHAR2(500)",
            "qualificacao_do_socio": "VARCHAR2(500)",
            "data_entrada_sociedade": "DATE",
            "pais": "VARCHAR2(3)",
            "representante_legal": "VARCHAR2(500)",
            "nome_do_representante": "VARCHAR2(500)",
            "quali_do_rep_legal": "VARCHAR2(500)",
            "faixa_etaria": "VARCHAR2(500)",
        },
    },
    "dados_simples": {
        "columns": [
            "cnpj_basico",
            "opcao_pelo_simples",
            "data_opcao_pelo_simples",
            "data_exclusao_do_simples",
            "opcao_pelo_mei",
            "data_opcao_pelo_mei",
            "data_exclusao_do_mei",
        ],
        "pk": ["cnpj_basico"],
        "oracle_types": {
            "cnpj_basico": "VARCHAR2(8)",
            "opcao_pelo_simples": "VARCHAR2(1)",
            "data_opcao_pelo_simples": "DATE",
            "data_exclusao_do_simples": "DATE",
            "opcao_pelo_mei": "VARCHAR2(1)",
            "data_opcao_pelo_mei": "DATE",
            "data_exclusao_do_mei": "DATE",
        },
    },
}


class OracleMigrator:
    """Migrates data from PostgreSQL staging tables to Oracle DB using python-oracledb."""

    def __init__(self, config: Config, table_prefix: str = "SG3_"):
        self.config = config
        self.table_prefix = table_prefix
        self.oracle_conn = None

    def connect_oracle(self):
        """Establish connection to Oracle DB in Thin mode."""
        if self.oracle_conn is not None:
            return

        dsn = oracledb.makedsn(
            host=self.config.oracle_host,
            port=self.config.oracle_port,
            service_name=self.config.oracle_service,
        )

        for attempt in range(4):
            try:
                self.oracle_conn = oracledb.connect(
                    user=self.config.oracle_user,
                    password=self.config.oracle_password,
                    dsn=dsn,
                )
                logger.info("Connected to Oracle DB successfully (Thin mode).")
                return
            except Exception as e:
                logger.warning(f"Oracle connection attempt {attempt+1} failed: {e}")
                if attempt == 3:
                    raise
                time.sleep(2**attempt)

    def disconnect_oracle(self):
        """Close Oracle connection."""
        if self.oracle_conn:
            try:
                self.oracle_conn.close()
            except Exception:
                pass
            self.oracle_conn = None

    def get_oracle_table_name(self, pg_table: str) -> str:
        """Get formatted Oracle table name."""
        return f"{self.table_prefix}{pg_table.upper()}"

    def get_available_tables(self) -> list:
        """Get list of available table names for Oracle migration."""
        return list(TABLE_SCHEMAS.keys())

    def ensure_oracle_tables(self, selected_tables: Optional[list] = None):
        """Ensure required tables and tracking table exist in Oracle DB."""
        self.connect_oracle()
        cursor = self.oracle_conn.cursor()

        # 1. Create tracking table SG3_PROCESSED_FILES if not exists
        tracking_table = self.get_oracle_table_name("processed_files")
        sql_tracking = f"""
        BEGIN
            EXECUTE IMMEDIATE 'CREATE TABLE {tracking_table} (
                directory VARCHAR2(50) NOT NULL,
                filename VARCHAR2(255) NOT NULL,
                processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (directory, filename)
            )';
        EXCEPTION
            WHEN OTHERS THEN
                IF SQLCODE != -955 THEN RAISE; END IF;
        END;
        """
        try:
            cursor.execute(sql_tracking)
            self.oracle_conn.commit()
        except Exception as e:
            logger.debug(f"Tracking table check: {e}")

        # 2. Create data tables
        target_tables = TABLE_SCHEMAS.items()
        if selected_tables is not None:
            target_tables = [(t, schema) for t, schema in TABLE_SCHEMAS.items() if t in selected_tables]

        for pg_table, schema in target_tables:
            oracle_table = self.get_oracle_table_name(pg_table)
            cols_ddl = []
            for col, otype in schema["oracle_types"].items():
                cols_ddl.append(f"{col.upper()} {otype}")

            pk_cols = ", ".join([pk.upper() for pk in schema["pk"]])
            ddl = f"""
            BEGIN
                EXECUTE IMMEDIATE 'CREATE TABLE {oracle_table} (
                    {", ".join(cols_ddl)},
                    DATA_ATUALIZACAO TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
                    PRIMARY KEY ({pk_cols})
                )';
            EXCEPTION
                WHEN OTHERS THEN
                    IF SQLCODE != -955 THEN RAISE; END IF;
            END;
            """
            try:
                cursor.execute(ddl)
                self.oracle_conn.commit()
            except Exception as e:
                logger.debug(f"Table {oracle_table} check: {e}")

        cursor.close()

    def get_processed_files(self, directory: str) -> set:
        """Get set of processed filenames for directory in Oracle."""
        self.connect_oracle()
        tracking_table = self.get_oracle_table_name("processed_files")
        cursor = self.oracle_conn.cursor()
        try:
            cursor.execute(
                f"SELECT filename FROM {tracking_table} WHERE directory = :1",
                [directory],
            )
            return {row[0] for row in cursor.fetchall()}
        except Exception:
            return set()
        finally:
            cursor.close()

    def mark_processed(self, directory: str, filename: str):
        """Mark a file as processed in Oracle tracking table."""
        self.connect_oracle()
        tracking_table = self.get_oracle_table_name("processed_files")
        cursor = self.oracle_conn.cursor()
        sql = f"""
        MERGE INTO {tracking_table} target
        USING (SELECT :1 AS directory, :2 AS filename FROM DUAL) src
        ON (target.directory = src.directory AND target.filename = src.filename)
        WHEN NOT MATCHED THEN
            INSERT (directory, filename, processed_at)
            VALUES (src.directory, src.filename, CURRENT_TIMESTAMP)
        """
        try:
            cursor.execute(sql, [directory, filename])
            self.oracle_conn.commit()
        finally:
            cursor.close()

    def build_merge_sql(self, pg_table: str) -> str:
        """Build dynamic MERGE INTO SQL statement for Oracle."""
        schema = TABLE_SCHEMAS[pg_table]
        oracle_table = self.get_oracle_table_name(pg_table)
        col_map = schema.get("column_map", {})
        cols = [col_map.get(c, c).upper() for c in schema["columns"]]
        pks = [col_map.get(pk, pk).upper() for pk in schema["pk"]]
        non_pks = [c for c in cols if c not in pks]

        select_cols = ", ".join([f":{i+1} AS {col}" for i, col in enumerate(cols)])
        on_clause = " AND ".join([f"target.{pk} = src.{pk}" for pk in pks])

        if non_pks:
            update_clause = ", ".join([f"target.{col} = src.{col}" for col in non_pks])
            update_clause += ", target.DATA_ATUALIZACAO = CURRENT_TIMESTAMP"
            matched_stmt = f"WHEN MATCHED THEN UPDATE SET {update_clause}"
        else:
            matched_stmt = ""

        insert_cols = ", ".join(cols) + ", DATA_ATUALIZACAO"
        insert_vals = ", ".join([f"src.{col}" for col in cols]) + ", CURRENT_TIMESTAMP"

        sql = f"""
        MERGE INTO {oracle_table} target
        USING (SELECT {select_cols} FROM DUAL) src
        ON ({on_clause})
        {matched_stmt}
        WHEN NOT MATCHED THEN
            INSERT ({insert_cols})
            VALUES ({insert_vals})
        """
        return sql

    def migrate_table_data(
        self,
        pg_conn,
        pg_table: str,
        directory: str,
        progress_callback: Optional[Callable[[int, str], None]] = None,
    ) -> int:
        """Stream data from PostgreSQL table to Oracle DB in batches."""
        if pg_table not in TABLE_SCHEMAS:
            logger.warning(f"Table {pg_table} not defined in Oracle schema map.")
            return 0

        self.connect_oracle()
        schema = TABLE_SCHEMAS[pg_table]
        cols = schema["columns"]
        cols_str = ", ".join([f'"{c}"' for c in cols])

        batch_size = self.config.oracle_batch_size
        merge_sql = self.build_merge_sql(pg_table)

        # Postgres server-side cursor for memory-safe streaming
        pg_cursor = pg_conn.cursor(name=f"stream_oracle_{pg_table}_{int(time.time())}")
        pg_cursor.itersize = batch_size
        pg_cursor.execute(f"SELECT {cols_str} FROM {pg_table}")

        oracle_cursor = self.oracle_conn.cursor()
        oracle_cursor.arraysize = batch_size

        total_migrated = 0

        try:
            while True:
                rows = pg_cursor.fetchmany(batch_size)
                if not rows:
                    break

                # Execute merge for batch
                oracle_cursor.executemany(merge_sql, rows)
                self.oracle_conn.commit()

                total_migrated += len(rows)
                if progress_callback:
                    progress_callback(total_migrated, pg_table)

                del rows
                gc.collect()

            logger.info(f"Migrated {total_migrated:,} rows from PG to Oracle table {pg_table}")
            return total_migrated

        except Exception as e:
            self.oracle_conn.rollback()
            logger.error(f"Error migrating table {pg_table} to Oracle: {e}")
            raise
        finally:
            try:
                pg_cursor.close()
            except Exception:
                pass
            oracle_cursor.close()
