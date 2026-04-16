from fastapi.testclient import TestClient

from app.core.roles import RoleName
from app.core.security import get_current_user, require_admin, require_staff
from app.main import app
from app.models.auth.role import Role
from app.models.auth.user import User
from app.models.career import Career
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


def test_me_returns_404_when_user_not_found(clear_dependency_overrides):
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        id=9999,
        role=RoleName.USER,
    )
    client = TestClient(app)

    response = client.get("/users/me")

    assert response.status_code == 404
    assert response.json()["detail"] == "Usuario no encontrado"


def test_update_my_career_not_found(db, clear_dependency_overrides):
    role = db.query(Role).filter(Role.name == RoleName.USER).one_or_none()
    if not role:
        role = Role(name=RoleName.USER)
        db.add(role)
        db.commit()

    user = User(
        email="career404@itmexicali.edu.mx",
        name="Career 404",
        oauth_provider="google",
        oauth_sub="career-404",
        id_role=role.id,
    )
    db.add(user)
    db.commit()

    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        id=user.id,
        role=RoleName.USER,
    )
    client = TestClient(app)

    response = client.patch("/users/me/career", json={"career_id": 9999})

    assert response.status_code == 404
    assert response.json()["detail"] == "Carrera no encontrada"


def test_update_my_career_user_not_found(db, clear_dependency_overrides):
    career = Career(name="Ingeniería en Sistemas")
    db.add(career)
    db.commit()
    db.refresh(career)

    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        id=9999,
        role=RoleName.USER,
    )
    client = TestClient(app)

    response = client.patch("/users/me/career", json={"career_id": career.id})

    assert response.status_code == 404
    assert response.json()["detail"] == "Usuario no encontrado"


def test_update_my_career_success(db, clear_dependency_overrides):
    role = db.query(Role).filter(Role.name == RoleName.USER).one_or_none()
    if not role:
        role = Role(name=RoleName.USER)
        db.add(role)
        db.commit()

    career = Career(name="Ingeniería Industrial")
    db.add(career)
    db.flush()

    user = User(
        email="career-ok@itmexicali.edu.mx",
        name="Career Ok",
        oauth_provider="google",
        oauth_sub="career-ok",
        id_role=role.id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        id=user.id,
        role=RoleName.USER,
    )
    client = TestClient(app)

    response = client.patch("/users/me/career", json={"career_id": career.id})

    assert response.status_code == 200
    assert response.json() == {"id_career": career.id}

    db.refresh(user)
    assert user.id_career == career.id


# ── GET /users ───────────────────────────────────────────────────────────────


def test_get_all_users_returns_list_for_admin(db, clear_dependency_overrides):
    role = db.query(Role).filter(Role.name == RoleName.USER).one_or_none()
    if not role:
        role = Role(name=RoleName.USER)
        db.add(role)
        db.commit()

    user = User(
        email="list-user@itmexicali.edu.mx",
        name="List User",
        oauth_provider="google",
        oauth_sub="list-user-1",
        id_role=role.id,
    )
    db.add(user)
    db.commit()

    app.dependency_overrides[require_admin] = lambda: CurrentUser(
        id=1,
        role=RoleName.ADMIN,
    )
    client = TestClient(app)

    response = client.get("/users")

    assert response.status_code == 200
    assert isinstance(response.json(), list)
    assert any(u["email"] == "list-user@itmexicali.edu.mx" for u in response.json())


def test_get_all_users_forbidden_for_non_admin(clear_dependency_overrides):
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        id=1,
        role=RoleName.USER,
    )
    client = TestClient(app)

    response = client.get("/users")

    assert response.status_code == 403
