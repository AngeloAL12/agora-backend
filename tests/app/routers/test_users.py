from fastapi.testclient import TestClient

from app.core.roles import RoleName
from app.core.security import get_current_user, require_admin, require_staff
from app.main import app
from app.schemas.auth.auth import CurrentUser


def test_me_returns_current_user(clear_dependency_overrides):
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        id=1,
        role=RoleName.USER,
    )
    client = TestClient(app)

    response = client.get("/users/me")

    assert response.status_code == 200
    assert response.json() == {"id": 1, "role": RoleName.USER}


def test_admin_returns_admin_user(clear_dependency_overrides):
    app.dependency_overrides[require_admin] = lambda: CurrentUser(
        id=1,
        role=RoleName.ADMIN,
    )
    client = TestClient(app)

    response = client.get("/users/admin")

    assert response.status_code == 200
    assert response.json() == {
        "message": "admin access",
        "user": {"id": 1, "role": RoleName.ADMIN},
    }


def test_staff_returns_staff_user(clear_dependency_overrides):
    app.dependency_overrides[require_staff] = lambda: CurrentUser(
        id=1,
        role=RoleName.STAFF,
    )
    client = TestClient(app)

    response = client.get("/users/staff")

    assert response.status_code == 200
    assert response.json() == {
        "message": "staff access",
        "user": {"id": 1, "role": RoleName.STAFF},
    }
