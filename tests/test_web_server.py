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
