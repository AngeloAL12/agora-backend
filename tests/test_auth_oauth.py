from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient
from jose import JWTError

from app.core.database import get_db
from app.core.security import get_current_user
from app.main import app
from app.schemas.auth.auth import CurrentUser


@pytest.fixture(autouse=True)
def override_dependency(db):
    app.dependency_overrides[get_db] = lambda: db
    yield
    app.dependency_overrides.clear()


# -----------------------------------------------------

client = TestClient(app)


def test_read_users_me_unauthorized():
    response = client.get("/auth/me")
    assert response.status_code == 401


# --- TESTS DE GOOGLE ---


@patch("google.oauth2.id_token.verify_oauth2_token")
def test_google_login_success(mock_verify, user_role):
    from app.core.config import settings

    mock_verify.return_value = {
        "aud": settings.GOOGLE_IOS_CLIENT_ID or settings.GOOGLE_CLIENT_ID,
        "email": "test@itmexicali.edu.mx",
        "name": "Test User",
        "sub": "google-123",
    }
    response = client.post("/auth/google/mobile-login", json={"token": "fake-token"})
    assert response.status_code == 200
    assert "access_token" in response.json()


@patch("google.oauth2.id_token.verify_oauth2_token")
def test_google_login_success_android_audience(mock_verify, user_role, monkeypatch):
    from app.core.config import settings

    # 1. Definimos un ID falso y se lo inyectamos a los settings usando monkeypatch
    fake_android_id = "android-test-id.apps.googleusercontent.com"
    monkeypatch.setattr(settings, "GOOGLE_ANDROID_CLIENT_ID", fake_android_id)

    # 2. Le decimos al mock que use ese mismo ID en el token
    mock_verify.return_value = {
        "aud": fake_android_id,
        "email": "android@itmexicali.edu.mx",
        "name": "Android User",
        "sub": "google-android-123",
    }

    response = client.post("/auth/google/mobile-login", json={"token": "fake-token"})

    # 3. Validamos que la respuesta sea exitosa
    assert response.status_code == 200
    assert "access_token" in response.json()


@patch("google.oauth2.id_token.verify_oauth2_token")
def test_google_login_invalid_domain(mock_verify, db):
    from app.core.config import settings

    mock_verify.return_value = {
        "aud": settings.GOOGLE_IOS_CLIENT_ID or settings.GOOGLE_CLIENT_ID,
        "email": "hacker@gmail.com",
        "name": "Hacker",
        "sub": "google-bad",
    }
    response = client.post("/auth/google/mobile-login", json={"token": "fake-token"})
    assert response.status_code == 403


@patch("google.oauth2.id_token.verify_oauth2_token")
def test_google_login_expired_token(mock_verify, db):
    mock_verify.side_effect = ValueError("Token expired")
    response = client.post("/auth/google/mobile-login", json={"token": "fake-token"})
    assert response.status_code == 401


@patch("google.oauth2.id_token.verify_oauth2_token")
def test_google_login_invalid_audience(mock_verify, db, monkeypatch):
    from app.core.config import settings

    # Ensure we have client IDs configured for the test
    monkeypatch.setattr(
        settings, "GOOGLE_CLIENT_ID", "valid-client-id.apps.googleusercontent.com"
    )
    monkeypatch.setattr(
        settings, "GOOGLE_IOS_CLIENT_ID", "valid-ios-id.apps.googleusercontent.com"
    )

    mock_verify.return_value = {
        "aud": "some-other-client-id.apps.googleusercontent.com",
        "email": "test@itmexicali.edu.mx",
        "name": "Wrong Audience",
        "sub": "google-wrong-aud",
    }
    response = client.post("/auth/google/mobile-login", json={"token": "fake-token"})
    assert response.status_code == 401


# --- TESTS DE MICROSOFT ---


@patch("app.routers.auth.auth._verify_microsoft_token")
def test_microsoft_login_success(mock_verify, user_role):
    mock_verify.return_value = {
        "email": "test@mexicali.tecnm.mx",
        "name": "Test MS",
        "sub": "ms-123",
    }
    response = client.post("/auth/microsoft/mobile-login", json={"token": "fake-token"})
    assert response.status_code == 200
    assert "access_token" in response.json()


@patch("app.routers.auth.auth._verify_microsoft_token")
def test_microsoft_login_invalid_domain(mock_verify, db):
    mock_verify.return_value = {
        "email": "hacker@hotmail.com",
        "name": "Hacker MS",
        "sub": "ms-bad",
    }
    response = client.post("/auth/microsoft/mobile-login", json={"token": "fake-token"})
    assert response.status_code == 403


@patch("app.routers.auth.auth._verify_microsoft_token")
def test_microsoft_login_invalid_token(mock_verify, db):
    mock_verify.side_effect = JWTError("Invalid token format")
    response = client.post("/auth/microsoft/mobile-login", json={"token": "fake-token"})
    assert response.status_code == 401


@patch("app.routers.auth.auth.verify_and_save_user")
@patch("google.oauth2.id_token.verify_oauth2_token")
def test_google_login_role_not_found_error(mock_verify, mock_save_user, db):
    from app.core.config import settings
    from app.services.auth.auth_service import RoleNotFoundError

    mock_verify.return_value = {
        "aud": settings.GOOGLE_IOS_CLIENT_ID or settings.GOOGLE_CLIENT_ID,
        "email": "test@itmexicali.edu.mx",
        "name": "Test User",
        "sub": "google-123",
    }
    mock_save_user.side_effect = RoleNotFoundError("Role not found")

    response = client.post("/auth/google/mobile-login", json={"token": "fake-token"})
    assert response.status_code == 500


@patch("app.routers.auth.auth.verify_and_save_user")
@patch("app.routers.auth.auth._verify_microsoft_token")
def test_microsoft_login_role_not_found_error(mock_verify_ms, mock_save_user, db):
    from app.services.auth.auth_service import RoleNotFoundError

    mock_verify_ms.return_value = {
        "email": "test@mexicali.tecnm.mx",
        "name": "Test MS User",
        "sub": "ms-123",
    }
    mock_save_user.side_effect = RoleNotFoundError("Role not found")

    response = client.post("/auth/microsoft/mobile-login", json={"token": "fake-token"})
    assert response.status_code == 500


def test_get_me_success(clear_dependency_overrides):
    from app.core.roles import RoleName

    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        id=1,
        role=RoleName.USER,
    )

    response = client.get("/auth/me")
    assert response.status_code == 200
    assert "id" in response.json()
    assert "role" in response.json()


def test_verify_microsoft_token_uses_jwks_endpoint(monkeypatch):
    from app.core.config import settings
    from app.routers.auth.auth import _verify_microsoft_token

    fake_response = Mock()
    fake_response.json.return_value = {"keys": [{"kid": "abc"}]}

    get_mock = Mock(return_value=fake_response)
    decode_mock = Mock(return_value={"sub": "ms-user"})

    monkeypatch.setattr("app.routers.auth.auth.http_requests.get", get_mock)
    monkeypatch.setattr("app.routers.auth.auth.jwt.decode", decode_mock)

    result = _verify_microsoft_token(
        token="ms-token",
        client_id=settings.MICROSOFT_CLIENT_ID,
        tenant_id=settings.MICROSOFT_TENANT_ID,
    )

    assert result == {"sub": "ms-user"}
    get_mock.assert_called_once_with(
        f"https://login.microsoftonline.com/{settings.MICROSOFT_TENANT_ID}/discovery/v2.0/keys",
        timeout=10,
    )
    decode_mock.assert_called_once()


def test_get_dev_token_returns_404_in_production_without_secret(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "ENV", "production")
    monkeypatch.setattr(settings, "API_TESTING_SECRET", "expected-secret")

    response = client.get("/auth/dev-token")

    assert response.status_code == 404
    assert response.json()["detail"] == "Not found"


def test_get_dev_token_returns_token_in_production_with_secret(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "ENV", "production")
    monkeypatch.setattr(settings, "API_TESTING_SECRET", "expected-secret")

    response = client.get("/auth/dev-token?testing_secret=expected-secret")

    assert response.status_code == 200
    assert "access_token" in response.json()
