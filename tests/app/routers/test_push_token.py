from fastapi.testclient import TestClient

from app.core.auth import get_current_user
from app.main import app
from tests.test_setup import insert_role, insert_user

client = TestClient(app)

def fake_user():
    class FakeUser:
        id = 1
    return FakeUser()

def test_push_token_creates_new_session():
    insert_role()
    insert_user()
    app.dependency_overrides[get_current_user] = fake_user

    response = client.post(
        "/push-token",
        json={"push_token": "abc123"},
        headers={"Authorization": "Bearer 1"},
    )

    assert response.status_code == 200
    assert response.json()["message"] == "Push token guardado correctamente"
    app.dependency_overrides = {}

def test_push_token_updates_existing_session():
    insert_role()
    insert_user()
    app.dependency_overrides[get_current_user] = fake_user

    client.post(
        "/push-token",
        json={"push_token": "first"},
        headers={"Authorization": "Bearer 1"},
    )

    response = client.post(
        "/push-token",
        json={"push_token": "updated"},
        headers={"Authorization": "Bearer 1"},
    )

    assert response.status_code == 200
    assert response.json()["message"] == "Push token guardado correctamente"
    app.dependency_overrides = {}