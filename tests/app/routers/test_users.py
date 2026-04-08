from fastapi.testclient import TestClient

from app.core.roles import RoleName
from app.core.security import get_current_user, require_admin, require_staff
from app.main import app
from app.models.auth.role import Role
from app.models.auth.user import User
from app.schemas.auth.auth import CurrentUser


def test_me_returns_current_user(db, clear_dependency_overrides):
    role = db.query(Role).filter(Role.name == RoleName.USER).one_or_none()
    if not role:
        role = Role(name=RoleName.USER)
        db.add(role)
        db.commit()

    user = User(
        email="test@itmexicali.edu.mx",
        name="Test User",
        oauth_provider="google",
        oauth_sub="1",
        id_role=role.id,
    )
    db.add(user)
    db.commit()

    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        id=user.id,
        role=RoleName.USER,
    )
    client = TestClient(app)

    response = client.get("/users/me")

    assert response.status_code == 200
    assert response.json() == {
        "name": "Test User",
        "clubs_count": 0,
        "complaints_count": 0,
        "likes_count": 0,
        "career": None,
        "photo": None,
    }


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
