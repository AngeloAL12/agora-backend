from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_main_test_route():
    response = client.get("/test")
    assert response.status_code == 200

