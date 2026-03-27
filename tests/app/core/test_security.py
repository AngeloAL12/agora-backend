from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.core.roles import RoleName
from app.core.security import (
    TokenDecodeError,
    create_access_token,
    decode_access_token,
    get_current_user,
    require_admin,
    require_staff,
)
from app.schemas.auth import CurrentUser


def test_create_access_token_returns_string():
    token = create_access_token({"sub": "1"})
    assert isinstance(token, str)
    assert token != ""


def test_create_access_token_and_decode_access_token():
    token = create_access_token({"sub": "1"})
    payload = decode_access_token(token)

    assert payload["sub"] == "1"
    assert "exp" in payload


def test_create_access_token_with_custom_expiration():
    token = create_access_token({"sub": "123"}, expires_delta=timedelta(minutes=5))
    payload = decode_access_token(token)

    assert payload["sub"] == "123"
    assert "exp" in payload


def test_decode_access_token_invalid_token():
    with pytest.raises(TokenDecodeError) as exc_info:
        decode_access_token("token-falso")

    assert str(exc_info.value) == "Token inválido"


def test_require_admin_allows_admin():
    user = CurrentUser(id=1, role=RoleName.ADMIN)
    result = require_admin(user)
    assert result == user


def test_require_admin_rejects_non_admin():
    user = CurrentUser(id=1, role=RoleName.USER)

    with pytest.raises(HTTPException) as exc_info:
        require_admin(user)

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "Solo admin"


def test_require_staff_allows_staff():
    user = CurrentUser(id=1, role=RoleName.STAFF)
    result = require_staff(user)
    assert result == user


def test_require_staff_allows_admin():
    user = CurrentUser(id=1, role=RoleName.ADMIN)
    result = require_staff(user)
    assert result == user


def test_require_staff_rejects_user():
    user = CurrentUser(id=1, role=RoleName.USER)

    with pytest.raises(HTTPException) as exc_info:
        require_staff(user)

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "Solo staff"


def test_get_current_user_success():
    fake_token = create_access_token({"sub": "1"})
    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer",
        credentials=fake_token,
    )

    fake_role = SimpleNamespace(name=RoleName.USER)
    fake_user = SimpleNamespace(id=1, is_active=True, role=fake_role)

    fake_query = MagicMock()
    fake_query.filter.return_value.first.return_value = fake_user

    fake_db = MagicMock()
    fake_db.query.return_value = fake_query

    result = get_current_user(credentials, fake_db)

    assert result.id == 1
    assert result.role == RoleName.USER


def test_get_current_user_invalid_sub():
    fake_token = create_access_token({"sub": "abc"})
    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer",
        credentials=fake_token,
    )
    fake_db = MagicMock()

    with pytest.raises(HTTPException) as exc_info:
        get_current_user(credentials, fake_db)

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Token inválido"


def test_get_current_user_user_not_found():
    fake_token = create_access_token({"sub": "1"})
    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer",
        credentials=fake_token,
    )

    fake_query = MagicMock()
    fake_query.filter.return_value.first.return_value = None

    fake_db = MagicMock()
    fake_db.query.return_value = fake_query

    with pytest.raises(HTTPException) as exc_info:
        get_current_user(credentials, fake_db)

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Usuario no encontrado"


def test_get_current_user_inactive_user():
    fake_token = create_access_token({"sub": "1"})
    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer",
        credentials=fake_token,
    )

    fake_role = SimpleNamespace(name=RoleName.USER)
    fake_user = SimpleNamespace(id=1, is_active=False, role=fake_role)

    fake_query = MagicMock()
    fake_query.filter.return_value.first.return_value = fake_user

    fake_db = MagicMock()
    fake_db.query.return_value = fake_query

    with pytest.raises(HTTPException) as exc_info:
        get_current_user(credentials, fake_db)

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "Usuario inactivo"


def test_get_current_user_without_role():
    fake_token = create_access_token({"sub": "1"})
    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer",
        credentials=fake_token,
    )

    fake_user = SimpleNamespace(id=1, is_active=True, role=None)

    fake_query = MagicMock()
    fake_query.filter.return_value.first.return_value = fake_user

    fake_db = MagicMock()
    fake_db.query.return_value = fake_query

    with pytest.raises(HTTPException) as exc_info:
        get_current_user(credentials, fake_db)

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "Usuario sin rol asignado"
