"""Configuration for CNPJ data pipeline."""

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()

@dataclass
class Config:
    """Pipeline configuration with sensible defaults."""

    database_url: str
    batch_size: int = 500000
    temp_dir: str = "./temp"
    download_workers: int = 4
    retry_attempts: int = 3
    retry_delay: int = 5
    connect_timeout: int = 30
    read_timeout: int = 300
    keep_files: bool = False
    base_url: str = "https://arquivos.receitafederal.gov.br/public.php/webdav"
    share_token: str = "YggdBLfdninEJX9"

    # Oracle Configuration
    oracle_host: str = ""
    oracle_port: int = 1521
    oracle_service: str = ""
    oracle_user: str = ""
    oracle_password: str = ""
    oracle_batch_size: int = 10000
    enable_oracle: bool = True

    # Web Dashboard & Schedule
    web_host: str = "0.0.0.0"
    web_port: int = 8000
    cron_schedule: str = "0 3 1 * *"  # Executa dia 1 de cada mês às 03:00

    @classmethod
    def from_env(cls) -> "Config":
        """Create config from environment variables."""
        return cls(
            database_url=os.getenv("DATABASE_URL", ""),
            batch_size=int(os.getenv("BATCH_SIZE", "500000")),
            temp_dir=os.getenv("TEMP_DIR", "./temp"),
            download_workers=int(os.getenv("DOWNLOAD_WORKERS", "4")),
            retry_attempts=int(os.getenv("RETRY_ATTEMPTS", "3")),
            retry_delay=int(os.getenv("RETRY_DELAY", "5")),
            connect_timeout=int(os.getenv("CONNECT_TIMEOUT", "30")),
            read_timeout=int(os.getenv("READ_TIMEOUT", "300")),
            keep_files=os.getenv("KEEP_DOWNLOADED_FILES", "false").lower() == "true",
            oracle_host=os.getenv("ORACLE_HOST", "192.168.1.225"),
            oracle_port=int(os.getenv("ORACLE_PORT", "1521")),
            oracle_service=os.getenv("ORACLE_SERVICE", ""),
            oracle_user=os.getenv("ORACLE_USER", ""),
            oracle_password=os.getenv("ORACLE_PASSWORD", ""),
            oracle_batch_size=int(os.getenv("ORACLE_BATCH_SIZE", "10000")),
            enable_oracle=os.getenv("ENABLE_ORACLE", "true").lower() == "true",
            web_host=os.getenv("WEB_HOST", "0.0.0.0"),
            web_port=int(os.getenv("WEB_PORT", "8000")),
            cron_schedule=os.getenv("CRON_SCHEDULE", "0 3 1 * *"),
        )



config = Config.from_env()
