from unittest.mock import MagicMock, patch
import pytest
from oracle_migrator import OracleMigrator, TABLE_SCHEMAS
from config import Config

@pytest.fixture
def mock_config():
    return Config(
        database_url="postgres://user:pass@localhost:5432/db",
        oracle_host="127.0.0.1",
        oracle_port=1521,
        oracle_service="ORBI",
        oracle_user="ORBI",
        oracle_password="password",
    )

def test_oracle_migrator_table_name(mock_config):
    migrator = OracleMigrator(mock_config, table_prefix="SG3_")
    assert migrator.get_oracle_table_name("empresas") == "SG3_EMPRESAS"
    assert migrator.get_oracle_table_name("socios") == "SG3_SOCIOS"

def test_build_merge_sql(mock_config):
    migrator = OracleMigrator(mock_config, table_prefix="SG3_")
    merge_sql = migrator.build_merge_sql("empresas")
    assert "MERGE INTO SG3_EMPRESAS" in merge_sql
    assert "WHEN MATCHED THEN UPDATE SET" in merge_sql
    assert "WHEN NOT MATCHED THEN" in merge_sql

def test_socios_column_mapping_and_identifier_length(mock_config):
    migrator = OracleMigrator(mock_config, table_prefix="SG3_")
    merge_sql = migrator.build_merge_sql("socios")
    assert "QUALI_DO_REP_LEGAL" in merge_sql
    assert "QUALIFICACAO_DO_REPRESENTANTE_LEGAL" not in merge_sql

    # Ensure all Oracle table columns and table names are <= 30 characters
    for pg_table, schema in TABLE_SCHEMAS.items():
        oracle_table = migrator.get_oracle_table_name(pg_table)
        assert len(oracle_table) <= 30, f"Table name {oracle_table} exceeds 30 chars"

        col_map = schema.get("column_map", {})
        for col in schema["columns"]:
            oracle_col = col_map.get(col, col)
            assert len(oracle_col) <= 30, f"Column {oracle_col} in table {pg_table} exceeds 30 chars"
