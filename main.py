#!/usr/bin/env python3
"""
CNPJ Data Pipeline - Download and process Brazilian company data from Receita Federal.

Usage:
    python main.py                    # Process latest month
    python main.py --list             # List available months
    python main.py --month 2024-11    # Process specific month
    python main.py --month 2024-11 --force   # Force re-process
    docker compose up                 # Run with Docker
"""

import argparse
import logging
import sys

from tqdm import tqdm

from config import config
from database import Database
from downloader import Downloader
from processor import get_file_type, process_file

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Processing order (respects foreign key dependencies)
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

def get_file_priority(filename: str) -> int:
    """Get processing priority for a file (lower = first)."""
    file_type = get_file_type(filename)
    if file_type in PROCESSING_ORDER:
        return PROCESSING_ORDER.index(file_type)
    return 999

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="CNPJ Data Pipeline - Download and process Brazilian company data")
    parser.add_argument("--list", "-l", action="store_true", help="List available months without processing")
    parser.add_argument("--month", "-m", type=str, help="Specific month to process (format: YYYY-MM, e.g., 2024-11)")
    parser.add_argument("--force", "-f", action="store_true", help="Force re-processing even if already processed")
    parser.add_argument("--web", "-w", action="store_true", help="Start Web Dashboard server and cyclic scheduler")
    parser.add_argument(
        "--stage",
        "-s",
        type=str,
        choices=["all", "postgres", "oracle"],
        default="all",
        help="Pipeline stage to execute: 'all' (default), 'postgres', or 'oracle'",
    )
    parser.add_argument(
        "--oracle-tables",
        "-t",
        nargs="+",
        help="Specific tables to migrate to Oracle DB (e.g. --oracle-tables empresas estabelecimentos)",
    )
    return parser.parse_args()

def main():
    """Main pipeline entry point."""
    args = parse_args()

    if args.web:
        import uvicorn
        logger.info(f"Iniciando Dashboard Web em http://{config.web_host}:{config.web_port}")
        uvicorn.run("web_server:app", host=config.web_host, port=config.web_port, reload=False)
        return

    downloader = Downloader(config)

    # Handle --list mode
    if args.list:
        available = downloader.get_available_directories()
        print("Available months:")
        for month in available:
            print(f"  {month}")
        return

    if not config.database_url:
        logger.error("DATABASE_URL not set")
        sys.exit(1)

    # Determine stages
    if args.stage == "postgres":
        stages = ["download_pg"]
    elif args.stage == "oracle":
        stages = ["oracle_migration"]
    else:
        stages = ["download_pg", "oracle_migration"]

    from scheduler import pipeline_manager
    try:
        pipeline_manager._execute_pipeline(
            target_month=args.month,
            force=args.force,
            stages=stages,
            oracle_tables=args.oracle_tables,
        )
    finally:
        downloader.cleanup()

if __name__ == "__main__":
    main()
