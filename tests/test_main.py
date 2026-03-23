from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_read_main():
    response = client.get("/")
    assert response.status_code == 200


def test_test_endpoint():
    response = client.get("/test")
    assert response.status_code == 200
