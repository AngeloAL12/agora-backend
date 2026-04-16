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
def test_microsoft_login_no_email(mock_verify, db):
    mock_verify.return_value = {
        "name": "No Email User",
        "sub": "ms-no-email",
    }
    response = client.post("/auth/microsoft/mobile-login", json={"token": "fake-token"})
    assert response.status_code == 403
    assert "No se encontró un correo válido" in response.json()["detail"]


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


# ── /auth/refresh ─────────────────────────────────────────────────────────────


@patch("google.oauth2.id_token.verify_oauth2_token")
def test_refresh_token_success(mock_verify, user_role, db):
    from app.core.config import settings

    mock_verify.return_value = {
        "aud": settings.GOOGLE_IOS_CLIENT_ID or settings.GOOGLE_CLIENT_ID,
        "email": "refresh-ok@itmexicali.edu.mx",
        "name": "Refresh User",
        "sub": "refresh-sub-ok",
    }
    login_resp = client.post("/auth/google/mobile-login", json={"token": "fake-token"})
    assert login_resp.status_code == 200
    refresh_token = login_resp.json()["refresh_token"]

    response = client.post("/auth/refresh", json={"refresh_token": refresh_token})
    assert response.status_code == 200
    assert "access_token" in response.json()
    assert "refresh_token" in response.json()


def test_refresh_token_invalid_token(db):
    response = client.post("/auth/refresh", json={"refresh_token": "not-a-real-token"})
    assert response.status_code == 401
    assert "inválido" in response.json()["detail"]


@patch("app.routers.auth.auth.decode_token")
def test_refresh_token_wrong_type(mock_decode, db):
    mock_decode.return_value = {"type": "access", "sub": "1"}
    response = client.post("/auth/refresh", json={"refresh_token": "some-token"})
    assert response.status_code == 401


@patch("app.routers.auth.auth.decode_token")
def test_refresh_token_no_sub(mock_decode, db):
    mock_decode.return_value = {"type": "refresh"}
    response = client.post("/auth/refresh", json={"refresh_token": "some-token"})
    assert response.status_code == 401


@patch("app.routers.auth.auth.decode_token")
def test_refresh_token_session_mismatch(mock_decode, db):
    from app.models.auth.role import Role
    from app.models.auth.user import User
    from app.models.auth.user_session import UserSession

    role = db.query(Role).filter(Role.name == "user").one_or_none()
    if not role:
        role = Role(name="user")
        db.add(role)
        db.flush()

    user = User(
        email="mismatch@itmexicali.edu.mx",
        oauth_provider="google",
        oauth_sub="mismatch-sub",
        name="Mismatch",
        id_role=role.id,
        is_active=True,
    )
    db.add(user)
    db.flush()

    session = UserSession(id_user=user.id, refresh_token="stored-token")
    db.add(session)
    db.commit()

    mock_decode.return_value = {"type": "refresh", "sub": str(user.id)}
    response = client.post("/auth/refresh", json={"refresh_token": "different-token"})
    assert response.status_code == 401


# ── /auth/logout ──────────────────────────────────────────────────────────────


@patch("google.oauth2.id_token.verify_oauth2_token")
def test_logout_clears_refresh_token(
    mock_verify, user_role, db, clear_dependency_overrides
):
    from app.core.config import settings
    from app.core.roles import RoleName
    from app.core.security import get_current_user
    from app.main import app as _app
    from app.schemas.auth.auth import CurrentUser

    mock_verify.return_value = {
        "aud": settings.GOOGLE_IOS_CLIENT_ID or settings.GOOGLE_CLIENT_ID,
        "email": "logout-ok@itmexicali.edu.mx",
        "name": "Logout User",
        "sub": "logout-sub-ok",
    }
    login_resp = client.post("/auth/google/mobile-login", json={"token": "fake-token"})
    assert login_resp.status_code == 200
    user_id = login_resp.json()["user"]["id"]

    _app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        id=user_id, role=RoleName.USER
    )

    response = client.post("/auth/logout")
    assert response.status_code == 200
    assert response.json()["message"] == "Sesión cerrada correctamente"

    from app.models.auth.user_session import UserSession

    session = db.query(UserSession).filter(UserSession.id_user == user_id).one_or_none()
    assert session is not None
    assert session.refresh_token is None


def test_logout_no_session_still_succeeds(clear_dependency_overrides):
    from app.core.roles import RoleName
    from app.core.security import get_current_user
    from app.main import app as _app
    from app.schemas.auth.auth import CurrentUser

    _app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        id=9999, role=RoleName.USER
    )
    response = client.post("/auth/logout")
    assert response.status_code == 200


# ── _save_refresh_token else branch ──────────────────────────────────────────


@patch("google.oauth2.id_token.verify_oauth2_token")
def test_google_login_creates_new_session_when_none_exists(mock_verify, user_role, db):
    from app.core.config import settings
    from app.models.auth.user import User
    from app.models.auth.user_session import UserSession

    mock_verify.return_value = {
        "aud": settings.GOOGLE_IOS_CLIENT_ID or settings.GOOGLE_CLIENT_ID,
        "email": "new-session@itmexicali.edu.mx",
        "name": "New Session User",
        "sub": "new-session-sub",
    }
    response = client.post("/auth/google/mobile-login", json={"token": "fake-token"})
    assert response.status_code == 200

    user = db.query(User).filter(User.email == "new-session@itmexicali.edu.mx").one()
    session = db.query(UserSession).filter(UserSession.id_user == user.id).one_or_none()
    assert session is not None
    assert session.refresh_token is not None


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
