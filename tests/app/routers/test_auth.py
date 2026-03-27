from unittest.mock import MagicMock

from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

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

    user_query = MagicMock()
    user_query.filter.return_value.first.return_value = None

    role_query = MagicMock()
    role_query.filter.return_value.first.return_value = fake_role

    fake_db = MagicMock()
    fake_db.query.side_effect = [user_query, role_query]
    fake_db.add.return_value = None
    fake_db.commit.return_value = None

    def fake_refresh(obj):
        obj.id = 2
        obj.role = fake_role
        obj.email = "new@gmail.com"
        obj.name = "New User"
        obj.photo = "https://foto.com/new.jpg"
        obj.oauth_provider = "google"
        obj.oauth_sub = "999999"
        obj.is_active = True

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


def test_login_returns_500_when_default_role_not_found():
    user_query = MagicMock()
    user_query.filter.return_value.first.return_value = None

    role_query = MagicMock()
    role_query.filter.return_value.first.return_value = None

    fake_db = MagicMock()
    fake_db.query.side_effect = [user_query, role_query]

    app.dependency_overrides[get_db] = lambda: fake_db
    client = TestClient(app)

    response = client.post(
        "/auth/login",
        json={
            "email": "norole@gmail.com",
            "name": "No Role",
            "photo": "https://foto.com/no-role.jpg",
            "oauth_provider": "google",
            "oauth_sub": "no-role-sub",
        },
    )

    assert response.status_code == 500
    assert response.json() == {
        "detail": "No existe el rol base 'user' en la base de datos"
    }

    app.dependency_overrides.clear()


def test_login_handles_integrity_error_and_recovers_existing_user():
    fake_role = MagicMock()
    fake_role.id = 1
    fake_role.name = "user"

    recovered_user = MagicMock()
    recovered_user.id = 3
    recovered_user.email = "recover@gmail.com"
    recovered_user.name = "Recovered User"
    recovered_user.photo = "https://foto.com/recovered.jpg"
    recovered_user.oauth_provider = "google"
    recovered_user.oauth_sub = "recover-sub"
    recovered_user.role = fake_role
    recovered_user.is_active = True

    initial_user_query = MagicMock()
    initial_user_query.filter.return_value.first.return_value = None

    role_query = MagicMock()
    role_query.filter.return_value.first.return_value = fake_role

    recovered_user_query = MagicMock()
    recovered_user_query.filter.return_value.first.return_value = recovered_user

    fake_db = MagicMock()
    fake_db.query.side_effect = [initial_user_query, role_query, recovered_user_query]
    fake_db.add.return_value = None
    fake_db.commit.side_effect = IntegrityError("dup", "params", "orig")
    fake_db.rollback.return_value = None

    app.dependency_overrides[get_db] = lambda: fake_db
    client = TestClient(app)

    response = client.post(
        "/auth/login",
        json={
            "email": "recover@gmail.com",
            "name": "Recovered User",
            "photo": "https://foto.com/recovered.jpg",
            "oauth_provider": "google",
            "oauth_sub": "recover-sub",
        },
    )

    assert response.status_code == 200

    body = response.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"
    assert body["user"]["id"] == 3
    assert body["user"]["role"] == "user"

    app.dependency_overrides.clear()


def test_login_returns_500_when_integrity_error_and_user_still_not_found():
    fake_role = MagicMock()
    fake_role.id = 1
    fake_role.name = "user"

    initial_user_query = MagicMock()
    initial_user_query.filter.return_value.first.return_value = None

    role_query = MagicMock()
    role_query.filter.return_value.first.return_value = fake_role

    recovered_user_query = MagicMock()
    recovered_user_query.filter.return_value.first.return_value = None

    fake_db = MagicMock()
    fake_db.query.side_effect = [initial_user_query, role_query, recovered_user_query]
    fake_db.add.return_value = None
    fake_db.commit.side_effect = IntegrityError("dup", "params", "orig")
    fake_db.rollback.return_value = None

    app.dependency_overrides[get_db] = lambda: fake_db
    client = TestClient(app)

    response = client.post(
        "/auth/login",
        json={
            "email": "broken@gmail.com",
            "name": "Broken User",
            "photo": "https://foto.com/broken.jpg",
            "oauth_provider": "google",
            "oauth_sub": "broken-sub",
        },
    )

    assert response.status_code == 500
    assert response.json() == {"detail": "No se pudo crear u obtener el usuario"}

    app.dependency_overrides.clear()


def test_login_updates_existing_user_when_data_changes():
    fake_role = MagicMock()
    fake_role.name = "user"

    existing_user = MagicMock()
    existing_user.id = 4
    existing_user.email = "old@gmail.com"
    existing_user.name = "Old Name"
    existing_user.photo = "https://foto.com/old.jpg"
    existing_user.oauth_provider = "google"
    existing_user.oauth_sub = "update-sub"
    existing_user.role = fake_role
    existing_user.is_active = True

    user_query = MagicMock()
    user_query.filter.return_value.first.return_value = existing_user

    fake_db = MagicMock()
    fake_db.query.return_value = user_query
    fake_db.commit.return_value = None
    fake_db.refresh.return_value = None

    app.dependency_overrides[get_db] = lambda: fake_db
    client = TestClient(app)

    response = client.post(
        "/auth/login",
        json={
            "email": "new@gmail.com",
            "name": "New Name",
            "photo": "https://foto.com/new.jpg",
            "oauth_provider": "google",
            "oauth_sub": "update-sub",
        },
    )

    assert response.status_code == 200

    body = response.json()
    assert body["user"]["id"] == 4
    assert body["user"]["email"] == "new@gmail.com"
    assert body["user"]["name"] == "New Name"
    assert body["user"]["role"] == "user"

    assert existing_user.email == "new@gmail.com"
    assert existing_user.name == "New Name"
    assert existing_user.photo == "https://foto.com/new.jpg"
    fake_db.commit.assert_called()
    fake_db.refresh.assert_called_with(existing_user)

    app.dependency_overrides.clear()


def test_login_existing_user_without_changes_does_not_commit():
    fake_role = MagicMock()
    fake_role.name = "user"

    existing_user = MagicMock()
    existing_user.id = 5
    existing_user.email = "same@gmail.com"
    existing_user.name = "Same User"
    existing_user.photo = "https://foto.com/same.jpg"
    existing_user.oauth_provider = "google"
    existing_user.oauth_sub = "same-sub"
    existing_user.role = fake_role
    existing_user.is_active = True

    user_query = MagicMock()
    user_query.filter.return_value.first.return_value = existing_user

    fake_db = MagicMock()
    fake_db.query.return_value = user_query

    app.dependency_overrides[get_db] = lambda: fake_db
    client = TestClient(app)

    response = client.post(
        "/auth/login",
        json={
            "email": "same@gmail.com",
            "name": "Same User",
            "photo": "https://foto.com/same.jpg",
            "oauth_provider": "google",
            "oauth_sub": "same-sub",
        },
    )

    assert response.status_code == 200

    body = response.json()
    assert body["user"]["id"] == 5
    assert body["user"]["role"] == "user"

    fake_db.commit.assert_not_called()
    fake_db.refresh.assert_not_called()

    app.dependency_overrides.clear()
