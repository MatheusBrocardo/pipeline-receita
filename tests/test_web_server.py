from fastapi.testclient import TestClient
from unittest.mock import patch
from web_server import app

client = TestClient(app)

def test_api_status():
    response = client.get("/api/status")
    assert response.status_code == 200
    data = response.json()
    assert "state" in data

@patch("web_server.Downloader.get_available_directories")
def test_api_months(mock_dirs):
    mock_dirs.return_value = ["2024-11", "2024-10"]
    response = client.get("/api/months")
    assert response.status_code == 200
    data = response.json()
    assert data["available_months"] == ["2024-11", "2024-10"]
    assert data["latest"] == "2024-11"

def test_api_tables():
    response = client.get("/api/tables")
    assert response.status_code == 200
    data = response.json()
    assert "tables" in data
    table_names = [t["name"] for t in data["tables"]]
    assert "empresas" in table_names
    assert "estabelecimentos" in table_names

@patch("web_server.pipeline_manager.run_pipeline")
def test_api_trigger_custom_stages_and_tables(mock_run):
    payload = {
        "month": "2024-11",
        "force": False,
        "stages": ["oracle_migration"],
        "oracle_tables": ["empresas", "estabelecimentos"]
    }
    response = client.post("/api/trigger", json=payload)
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    mock_run.assert_called_once_with(
        target_month="2024-11",
        force=False,
        stages=["oracle_migration"],
        oracle_tables=["empresas", "estabelecimentos"]
    )
