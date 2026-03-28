from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from jose import JWTError

from app.core.database import get_db
from app.main import app
from app.models.auth.role import Role


@pytest.fixture(autouse=True)
def override_dependency(db):
    app.dependency_overrides[get_db] = lambda: db
    yield
    app.dependency_overrides.clear()


# -----------------------------------------------------

client = TestClient(app)


def test_read_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Welcome to the Agora API!"}


def test_read_users_me_unauthorized():
    response = client.get("/auth/me")
    assert response.status_code == 401


# --- TESTS DE GOOGLE ---


@patch("google.oauth2.id_token.verify_oauth2_token")
def test_google_login_success(mock_verify, db):
    if not db.query(Role).filter(Role.name == "user").first():
        db.add(Role(name="user"))
        db.commit()

    mock_verify.return_value = {
        "email": "test@itmexicali.edu.mx",
        "name": "Test User",
        "sub": "google-123",
    }
    response = client.post("/auth/google/mobile-login", json={"token": "fake-token"})
    assert response.status_code == 200
    assert "access_token" in response.json()


@patch("google.oauth2.id_token.verify_oauth2_token")
def test_google_login_invalid_domain(mock_verify, db):
    mock_verify.return_value = {
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


# --- TESTS DE MICROSOFT ---


@patch("jose.jwt.get_unverified_claims")
def test_microsoft_login_success(mock_jwt, db):
    if not db.query(Role).filter(Role.name == "user").first():
        db.add(Role(name="user"))  # <-- Solo deja el 'name'
        db.commit()

    mock_jwt.return_value = {
        "email": "test@mexicali.tecnm.mx",
        "name": "Test MS",
        "sub": "ms-123",
    }
    response = client.post("/auth/microsoft/mobile-login", json={"token": "fake-token"})
    assert response.status_code == 200
    assert "access_token" in response.json()


@patch("jose.jwt.get_unverified_claims")
def test_microsoft_login_invalid_domain(mock_jwt, db):
    mock_jwt.return_value = {
        "email": "hacker@hotmail.com",
        "name": "Hacker MS",
        "sub": "ms-bad",
    }
    response = client.post("/auth/microsoft/mobile-login", json={"token": "fake-token"})
    assert response.status_code == 403


@patch("jose.jwt.get_unverified_claims")
def test_microsoft_login_invalid_token(mock_jwt, db):
    mock_jwt.side_effect = JWTError("Invalid token format")
    response = client.post("/auth/microsoft/mobile-login", json={"token": "fake-token"})
    assert response.status_code == 401
