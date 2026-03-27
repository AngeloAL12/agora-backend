from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from app.core.database import get_db
from app.main import app


def test_login_existing_user():
    fake_role = MagicMock()
    fake_role.name = "user"

    fake_user = MagicMock()
    fake_user.id = 1
    fake_user.email = "samy@gmail.com"
    fake_user.name = "Samy Ramos"
    fake_user.photo = "https://foto.com/avatar.jpg"
    fake_user.oauth_provider = "google"
    fake_user.oauth_sub = "123456789"
    fake_user.role = fake_role
    fake_user.is_active = True

    fake_query = MagicMock()
    fake_query.filter.return_value.first.return_value = fake_user

    fake_db = MagicMock()
    fake_db.query.return_value = fake_query

    app.dependency_overrides[get_db] = lambda: fake_db
    client = TestClient(app)

    response = client.post(
        "/auth/login",
        json={
            "email": "samy@gmail.com",
            "name": "Samy Ramos",
            "photo": "https://foto.com/avatar.jpg",
            "oauth_provider": "google",
            "oauth_sub": "123456789",
        },
    )

    assert response.status_code == 200

    body = response.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"
    assert body["user"]["id"] == 1
    assert body["user"]["role"] == "user"

    app.dependency_overrides.clear()


def test_login_creates_user_when_not_exists():
    fake_role = MagicMock()
    fake_role.id = 1
    fake_role.name = "user"

    created_user = MagicMock()
    created_user.id = 2
    created_user.email = "new@gmail.com"
    created_user.name = "New User"
    created_user.photo = "https://foto.com/new.jpg"
    created_user.oauth_provider = "google"
    created_user.oauth_sub = "999999"
    created_user.role = fake_role
    created_user.is_active = True

    user_query = MagicMock()
    user_query.filter.return_value.first.return_value = None

    role_query = MagicMock()
    role_query.filter.return_value.first.return_value = fake_role

    fake_db = MagicMock()
    fake_db.query.side_effect = [user_query, role_query]
    fake_db.add.return_value = None
    fake_db.commit.return_value = None

    def fake_refresh(obj):
        obj.id = created_user.id
        obj.role = created_user.role
        obj.email = created_user.email
        obj.name = created_user.name
        obj.photo = created_user.photo
        obj.oauth_provider = created_user.oauth_provider
        obj.oauth_sub = created_user.oauth_sub
        obj.is_active = created_user.is_active

    fake_db.refresh.side_effect = fake_refresh

    app.dependency_overrides[get_db] = lambda: fake_db
    client = TestClient(app)

    response = client.post(
        "/auth/login",
        json={
            "email": "new@gmail.com",
            "name": "New User",
            "photo": "https://foto.com/new.jpg",
            "oauth_provider": "google",
            "oauth_sub": "999999",
        },
    )

    assert response.status_code == 200

    body = response.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"
    assert body["user"]["id"] == 2
    assert body["user"]["email"] == "new@gmail.com"
    assert body["user"]["role"] == "user"

    app.dependency_overrides.clear()