from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.roles import RoleName
from app.core.security import get_current_user, require_admin
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
        "id": user.id,
        "email": "test@itmexicali.edu.mx",
        "role": RoleName.USER,
        "name": "Test User",
        "clubs_count": 0,
        "complaints_count": 0,
        "likes_count": 0,
        "career": None,
        "photo": None,
    }


def test_me_returns_404_when_user_does_not_exist(clear_dependency_overrides):
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        id=9999,
        role=RoleName.USER,
    )
    client = TestClient(app)

    response = client.get("/users/me")

    assert response.status_code == 404
    assert response.json()["detail"] == "Usuario no encontrado"


def test_patch_me_updates_name_and_career(db, clear_dependency_overrides):
    role = db.query(Role).filter(Role.name == RoleName.USER).one_or_none()
    if not role:
        role = Role(name=RoleName.USER)
        db.add(role)
        db.commit()

    career = Career(name="Ingeniería Industrial")
    db.add(career)
    db.commit()
    db.refresh(career)

    user = User(
        email="patch@itmexicali.edu.mx",
        name="Patch User",
        oauth_provider="google",
        oauth_sub="patch-user",
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

    response = client.patch(
        "/users/me",
        data={"name": "Updated Patch User", "id_career": career.id},
    )

    assert response.status_code == 200
    assert response.json()["name"] == "Updated Patch User"
    assert response.json()["career"] == "Ingeniería Industrial"
    assert response.json()["id"] == user.id
    assert response.json()["email"] == "patch@itmexicali.edu.mx"
    assert response.json()["role"] == RoleName.USER


def test_patch_me_returns_404_when_user_does_not_exist(clear_dependency_overrides):
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        id=9999,
        role=RoleName.USER,
    )
    client = TestClient(app)

    response = client.patch(
        "/users/me",
        data={"name": "Updated Patch User"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Usuario no encontrado"


def test_patch_me_invalid_career_returns_404(db, clear_dependency_overrides):
    role = db.query(Role).filter(Role.name == RoleName.USER).one_or_none()
    if not role:
        role = Role(name=RoleName.USER)
        db.add(role)
        db.commit()

    user = User(
        email="invalid-career@itmexicali.edu.mx",
        name="Career User",
        oauth_provider="google",
        oauth_sub="invalid-career-user",
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

    response = client.patch(
        "/users/me",
        data={"id_career": 9999},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Carrera no encontrada"


def test_patch_me_blank_name_keeps_existing_name(db, clear_dependency_overrides):
    role = db.query(Role).filter(Role.name == RoleName.USER).one_or_none()
    if not role:
        role = Role(name=RoleName.USER)
        db.add(role)
        db.commit()

    user = User(
        email="blank-name@itmexicali.edu.mx",
        name="Stable Name",
        oauth_provider="google",
        oauth_sub="blank-name-user",
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

    response = client.patch(
        "/users/me",
        data={"name": "   "},
    )

    assert response.status_code == 200
    assert response.json()["name"] == "Stable Name"


def test_patch_me_uploads_first_photo_without_delete(
    db, clear_dependency_overrides, monkeypatch
):
    role = db.query(Role).filter(Role.name == RoleName.USER).one_or_none()
    if not role:
        role = Role(name=RoleName.USER)
        db.add(role)
        db.commit()

    user = User(
        email="first-photo@itmexicali.edu.mx",
        name="First Photo User",
        oauth_provider="google",
        oauth_sub="first-photo-user",
        id_role=role.id,
        photo=None,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        id=user.id,
        role=RoleName.USER,
    )
    client = TestClient(app)

    called = {"deleted": False}

    async def fake_upload_file(file, bucket_name, prefix):
        del file
        assert bucket_name == settings.R2_BUCKET_PUBLIC
        assert prefix == f"users/{user.id}/photo"
        return f"users/{user.id}/photo/new.png"

    async def fake_delete_file(bucket_name, object_key):
        del bucket_name, object_key
        called["deleted"] = True

    monkeypatch.setattr(
        "app.routers.auth.users.storage_service.upload_file",
        fake_upload_file,
    )
    monkeypatch.setattr(
        "app.routers.auth.users.storage_service.delete_file",
        fake_delete_file,
    )

    response = client.patch(
        "/users/me",
        files={"photo": ("new.png", b"fake-image", "image/png")},
    )

    assert response.status_code == 200
    assert called["deleted"] is False


def test_patch_me_uploads_photo_and_deletes_previous_public_image(
    db, clear_dependency_overrides, monkeypatch
):
    role = db.query(Role).filter(Role.name == RoleName.USER).one_or_none()
    if not role:
        role = Role(name=RoleName.USER)
        db.add(role)
        db.commit()

    user = User(
        email="photo@itmexicali.edu.mx",
        name="Photo User",
        oauth_provider="google",
        oauth_sub="photo-user",
        id_role=role.id,
        photo="users/1/photo/old.png",
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        id=user.id,
        role=RoleName.USER,
    )
    client = TestClient(app)

    async def fake_upload_file(file, bucket_name, prefix):
        return "users/1/photo/new.png"

    async def fake_delete_file(bucket_name, object_key):
        assert bucket_name == settings.R2_BUCKET_PUBLIC
        assert object_key == "users/1/photo/old.png"  # stored key, no URL prefix

    monkeypatch.setattr(
        "app.routers.auth.users.storage_service.upload_file",
        fake_upload_file,
    )
    monkeypatch.setattr(
        "app.routers.auth.users.storage_service.delete_file",
        fake_delete_file,
    )

    response = client.patch(
        "/users/me",
        files={"photo": ("new.png", b"fake-image", "image/png")},
    )

    base = (
        settings.R2_PUBLIC_URL or f"{settings.R2_ENDPOINT}/{settings.R2_BUCKET_PUBLIC}"
    ).rstrip("/")
    assert response.status_code == 200
    assert response.json()["photo"] == f"{base}/users/1/photo/new.png"


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


def test_admin_endpoint_returns_payload(clear_dependency_overrides):
    app.dependency_overrides[require_admin] = lambda: CurrentUser(
        id=7,
        role=RoleName.ADMIN,
    )
    client = TestClient(app)

    response = client.get("/users/admin")

    assert response.status_code == 200
    assert response.json()["message"] == "admin access"
    assert response.json()["user"]["id"] == 7


def test_staff_endpoint_returns_payload(clear_dependency_overrides):
    from app.core.security import require_staff

    app.dependency_overrides[require_staff] = lambda: CurrentUser(
        id=8,
        role=RoleName.STAFF,
    )
    client = TestClient(app)

    response = client.get("/users/staff")

    assert response.status_code == 200
    assert response.json()["message"] == "staff access"
    assert response.json()["user"]["id"] == 8
