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
    assert response.headers["x-cache"] == "MISS"
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


def test_me_returns_cached_payload(clear_dependency_overrides, monkeypatch):
    cached_payload = {
        "id": 42,
        "email": "cached@itmexicali.edu.mx",
        "role": RoleName.USER,
        "name": "Cached User",
        "clubs_count": 3,
        "complaints_count": 1,
        "likes_count": 0,
        "career": "Ingeniería en Sistemas",
        "photo": "https://cdn.example/users/42/photo.png",
    }

    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        id=42,
        role=RoleName.USER,
    )
    monkeypatch.setattr(
        "app.routers.auth.users.cache_service.get_json_with_status",
        lambda _key: (cached_payload, "hit"),
    )

    client = TestClient(app)
    response = client.get("/users/me")

    assert response.status_code == 200
    assert response.headers["x-cache"] == "HIT"
    assert response.json() == cached_payload


def test_me_returns_db_when_cache_misses(db, clear_dependency_overrides, monkeypatch):
    role = db.query(Role).filter(Role.name == RoleName.USER).one_or_none()
    if not role:
        role = Role(name=RoleName.USER)
        db.add(role)
        db.commit()

    user = User(
        email="miss@itmexicali.edu.mx",
        name="Miss User",
        oauth_provider="google",
        oauth_sub="cache-miss-1",
        id_role=role.id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        id=user.id,
        role=RoleName.USER,
    )
    monkeypatch.setattr(
        "app.routers.auth.users.cache_service.get_json_with_status",
        lambda _key: (None, "miss"),
    )
    monkeypatch.setattr(
        "app.routers.auth.users.cache_service.set_json",
        lambda _key, _value, _ttl: None,
    )

    client = TestClient(app)
    response = client.get("/users/me")

    assert response.status_code == 200
    assert response.headers["x-cache"] == "MISS"
    assert response.json()["id"] == user.id
    assert response.json()["email"] == "miss@itmexicali.edu.mx"


def test_me_returns_db_when_cache_bypassed(db, clear_dependency_overrides, monkeypatch):
    role = db.query(Role).filter(Role.name == RoleName.USER).one_or_none()
    if not role:
        role = Role(name=RoleName.USER)
        db.add(role)
        db.commit()

    user = User(
        email="bypass@itmexicali.edu.mx",
        name="Bypass User",
        oauth_provider="google",
        oauth_sub="cache-bypass-1",
        id_role=role.id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        id=user.id,
        role=RoleName.USER,
    )
    monkeypatch.setattr(
        "app.routers.auth.users.cache_service.get_json_with_status",
        lambda _key: (None, "bypass"),
    )
    monkeypatch.setattr(
        "app.routers.auth.users.cache_service.set_json",
        lambda _key, _value, _ttl: None,
    )

    client = TestClient(app)
    response = client.get("/users/me")

    assert response.status_code == 200
    assert response.headers["x-cache"] == "BYPASS"
    assert response.json()["id"] == user.id


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


def test_patch_me_invalidates_user_me_cache(
    db, clear_dependency_overrides, monkeypatch
):
    role = db.query(Role).filter(Role.name == RoleName.USER).one_or_none()
    if not role:
        role = Role(name=RoleName.USER)
        db.add(role)
        db.commit()

    user = User(
        email="invalidate@itmexicali.edu.mx",
        name="Invalidate User",
        oauth_provider="google",
        oauth_sub="invalidate-user",
        id_role=role.id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        id=user.id,
        role=RoleName.USER,
    )

    deleted_keys = []
    monkeypatch.setattr(
        "app.routers.auth.users.cache_service.delete",
        lambda key: deleted_keys.append(key),
    )

    client = TestClient(app)
    response = client.patch("/users/me", data={"name": "Updated"})

    assert response.status_code == 200
    assert deleted_keys == [f"users:me:v1:{user.id}"]


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


def test_update_my_career_invalidates_user_me_cache(
    db, clear_dependency_overrides, monkeypatch
):
    role = db.query(Role).filter(Role.name == RoleName.USER).one_or_none()
    if not role:
        role = Role(name=RoleName.USER)
        db.add(role)
        db.commit()

    career = Career(name="Ing. Electrónica")
    db.add(career)
    db.flush()

    user = User(
        email="career-invalidate@itmexicali.edu.mx",
        name="Career Invalidate",
        oauth_provider="google",
        oauth_sub="career-invalidate",
        id_role=role.id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        id=user.id,
        role=RoleName.USER,
    )

    deleted_keys = []
    monkeypatch.setattr(
        "app.routers.auth.users.cache_service.delete",
        lambda key: deleted_keys.append(key),
    )

    client = TestClient(app)
    response = client.patch("/users/me/career", json={"career_id": career.id})

    assert response.status_code == 200
    assert deleted_keys == [f"users:me:v1:{user.id}"]


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
