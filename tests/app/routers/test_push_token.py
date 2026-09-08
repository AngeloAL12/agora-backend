import pytest
from fastapi.testclient import TestClient

from app.core.roles import RoleName
from app.core.security import get_current_user
from app.main import app
from app.models.auth.role import Role
from app.models.auth.user import User
from app.schemas.auth.auth import CurrentUser

client = TestClient(app)


@pytest.fixture
def test_user(db):
    role = Role(name="user")
    db.add(role)
    db.flush()

    user = User(
        email="test@example.com",
        oauth_provider="test",
        oauth_sub="sub123",
        name="Test User",
        id_role=role.id,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def mock_user(test_user):
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        id=test_user.id, role=RoleName.USER
    )
    yield
    app.dependency_overrides.pop(get_current_user, None)


def test_push_token_creates_new_session(mock_user):
    response = client.post("/push-token", json={"push_token": "abc123"})
    assert response.status_code == 200
    assert response.json()["message"] == "Push token guardado correctamente"


def test_push_token_updates_existing_session(mock_user):
    client.post("/push-token", json={"push_token": "first"})
    response = client.post("/push-token", json={"push_token": "updated"})
    assert response.status_code == 200
    assert response.json()["message"] == "Push token guardado correctamente"


def test_push_token_rejects_empty_string(mock_user):
    response = client.post("/push-token", json={"push_token": ""})
    assert response.status_code == 422
