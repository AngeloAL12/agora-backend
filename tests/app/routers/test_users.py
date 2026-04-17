from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.roles import RoleName
from app.core.security import get_current_user
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
        photo=f"{settings.R2_ENDPOINT}/{settings.R2_BUCKET_PUBLIC}/users/1/photo/old.png",
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
        assert object_key == "users/1/photo/old.png"

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
    assert response.json()["photo"].endswith(
        f"/{settings.R2_BUCKET_PUBLIC}/users/1/photo/new.png"
    )


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
