from unittest.mock import MagicMock

from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.core.database import get_db
from app.main import app

client = TestClient(app)


def test_health_ok():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_db_ok(db):
    app.dependency_overrides[get_db] = lambda: db
    response = client.get("/health/db")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    app.dependency_overrides.clear()


def test_health_db_error():
    def broken_db():
        mock = MagicMock()
        mock.execute.side_effect = OperationalError("conn failed", None, None)
        yield mock

    app.dependency_overrides[get_db] = broken_db
    response = client.get("/health/db")
    assert response.status_code == 503
    app.dependency_overrides.clear()
