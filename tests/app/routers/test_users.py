from fastapi.testclient import TestClient

from app.core.security import (
    CurrentUser,
    get_current_user,
    require_admin,
    require_staff,
)
from app.main import app


def test_me_returns_current_user():
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(id=1, role="user")
    client = TestClient(app)

    response = client.get("/users/me")

    assert response.status_code == 200
    assert response.json() == {"id": 1, "role": "user"}

    app.dependency_overrides.clear()


def test_admin_returns_admin_user():
    app.dependency_overrides[require_admin] = lambda: CurrentUser(id=1, role="admin")
    client = TestClient(app)

    response = client.get("/users/admin")

    assert response.status_code == 200
    assert response.json() == {
        "message": "admin access",
        "user": {"id": 1, "role": "admin"},
    }

    app.dependency_overrides.clear()


def test_staff_returns_staff_user():
    app.dependency_overrides[require_staff] = lambda: CurrentUser(id=1, role="staff")
    client = TestClient(app)

    response = client.get("/users/staff")

    assert response.status_code == 200
    assert response.json() == {
        "message": "staff access",
        "user": {"id": 1, "role": "staff"},
    }

    app.dependency_overrides.clear()
