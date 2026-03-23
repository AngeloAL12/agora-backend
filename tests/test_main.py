from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.main import app

client = TestClient(app)


def test_read_main():
    response = client.get("/")
    assert response.status_code == 200


def test_test_endpoint():
    response = client.get("/test")
    assert response.status_code == 200


def test_health_check_db_success():
    """Test health check endpoint returns 200 when database is connected."""
    response = client.get("/health/db")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["database"] == "connected"
    assert "details" in data
    assert "dialect" in data["details"]
    assert "driver" in data["details"]


def test_health_check_db_connection_failure():
    """Test health check endpoint returns 503 when database connection fails."""
    with patch("app.main.get_db") as mock_get_db:
        mock_session = MagicMock()
        mock_session.execute.side_effect = OperationalError(
            "connection failed", [], Exception("connection failed")
        )
        mock_get_db.return_value = iter([mock_session])

        response = client.get("/health/db")
        assert response.status_code == 503
        data = response.json()
        assert "detail" in data
        assert data["detail"]["status"] == "unhealthy"
        assert data["detail"]["database"] == "connection failed"


def test_health_check_db_generic_error():
    """Test health check endpoint returns 500 on unexpected errors."""
    with patch("app.main.get_db") as mock_get_db:
        mock_session = MagicMock()
        mock_session.execute.side_effect = Exception("unexpected error")
        mock_get_db.return_value = iter([mock_session])

        response = client.get("/health/db")
        assert response.status_code == 500
        data = response.json()
        assert "detail" in data
        assert data["detail"]["status"] == "error"
        assert data["detail"]["database"] == "unknown error"
