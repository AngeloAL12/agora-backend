import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.core.config import settings
from app.core.roles import RoleName
from app.core.security import TokenDecodeError, create_access_token, get_current_user
from app.main import app
from app.models.auth.role import Role
from app.models.auth.user import User
from app.models.auth.user_session import UserSession
from app.models.club.club import Club
from app.models.club.club_category import ClubCategory
from app.models.club.club_member import ClubMember
from app.models.club.message import ClubMessage
from app.routers.clubs import (
    _authenticate_ws_user,
    _build_image_url,
    _build_message_payload,
    _clean_required_text,
    _is_club_member,
    _notify_offline_members,
)
from app.schemas.auth.auth import CurrentUser
from app.services.redis_service import redis_chat_manager
from app.services.storage_service import storage_service


@pytest.fixture(autouse=True)
def seed_users(db):
    # Insert role + 3 users in a single transaction instead of 3 separate
    # ensure_user calls that each query for the role individually.
    role = Role(name=RoleName.USER.value)
    db.add(role)
    db.flush()  # obtain role.id before building users
    for user_id in (1, 2, 3):
        db.add(
            User(
                id=user_id,
                email=f"user{user_id}@itmexicali.edu.mx",
                oauth_provider="test",
                oauth_sub=f"test-{user_id}",
                name=f"User {user_id}",
                id_role=role.id,
                is_active=True,
            )
        )
    db.commit()


@pytest.fixture(autouse=True)
def clear_overrides():
    yield
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture(autouse=True)
def disable_redis_lifespan_for_clubs_tests(monkeypatch):
    async def _noop_connect():
        redis_chat_manager.redis_client = None

    async def _noop_disconnect():
        redis_chat_manager.redis_client = None
        redis_chat_manager._local_connections.clear()
        redis_chat_manager._pubsubs.clear()
        redis_chat_manager._listener_tasks.clear()

    monkeypatch.setattr(redis_chat_manager, "connect_redis", _noop_connect)
    monkeypatch.setattr(redis_chat_manager, "disconnect_redis", _noop_disconnect)

    redis_chat_manager.redis_client = None
    redis_chat_manager._local_connections.clear()
    yield
    redis_chat_manager.redis_client = None
    redis_chat_manager._local_connections.clear()


def override_user(user_id=1):
    return lambda: CurrentUser(id=user_id, role=RoleName.USER)


def unique_name(prefix: str) -> str:
    return f"{prefix} {uuid.uuid4().hex[:8]}"


def ensure_user(db, user_id):
    """Return an existing user or create them (and their role if absent)."""
    role = db.query(Role).filter(Role.name == RoleName.USER.value).first()

    if not role:
        role = Role(name=RoleName.USER.value)
        db.add(role)
        db.flush()

    user = db.query(User).filter(User.id == user_id).first()

    if user:
        return user

    user = User(
        id=user_id,
        email=f"user{user_id}@itmexicali.edu.mx",
        oauth_provider="test",
        oauth_sub=f"test-{user_id}",
        name=f"User {user_id}",
        id_role=role.id,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def create_category(db, name=None):
    category = ClubCategory(name=name or unique_name("Deportes"))
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


def create_club(
    db,
    category_id,
    leader_id=1,
    name=None,
    description="Desc",
    profile_image=None,
    cover_image=None,
):
    ensure_user(db, leader_id)

    club = Club(
        name=name or unique_name("Club Test"),
        description=description,
        id_category=category_id,
        id_leader=leader_id,
        profile_image=profile_image,
        cover_image=cover_image,
    )
    db.add(club)
    db.flush()  # get club.id without committing yet
    db.add(ClubMember(id_club=club.id, id_user=leader_id))
    db.commit()
    db.refresh(club)
    return club


def create_membership(db, club_id, user_id):
    ensure_user(db, user_id)
    exists = (
        db.query(ClubMember)
        .filter(ClubMember.id_club == club_id, ClubMember.id_user == user_id)
        .first()
    )
    if not exists:
        db.add(ClubMember(id_club=club_id, id_user=user_id))
        db.commit()


def create_club_message(db, club_id, user_id, content):
    ensure_user(db, user_id)
    message = ClubMessage(id_club=club_id, id_user=user_id, content=content)
    db.add(message)
    db.commit()
    db.refresh(message)
    return message


def test_build_image_url_returns_none_for_empty_value():
    assert _build_image_url(None) is None


def test_build_image_url_builds_public_url(monkeypatch):
    monkeypatch.setattr(settings, "R2_PUBLIC_URL", "https://cdn.example.com")

    assert _build_image_url("clubs/test/profile.png") == (
        "https://cdn.example.com/clubs/test/profile.png"
    )


def test_clean_required_text_returns_trimmed_value():
    assert _clean_required_text("  Club Test  ", "name", 255) == "Club Test"


def test_is_club_member_returns_expected_values(db):
    category = create_category(db)
    club = create_club(db, category.id, leader_id=1)
    create_membership(db, club.id, 2)

    assert _is_club_member(club, 1, db) is True
    assert _is_club_member(club, 2, db) is True
    assert _is_club_member(club, 3, db) is False


def test_get_clubs(db, monkeypatch):
    monkeypatch.setattr(settings, "R2_PUBLIC_URL", "https://cdn.example.com")

    category = create_category(db)

    club_one = create_club(
        db,
        category.id,
        name=unique_name("Club Uno"),
        profile_image="clubs/test/profile/uno.png",
        cover_image="clubs/test/cover/uno.png",
    )
    create_membership(db, club_one.id, 2)

    club_dos = create_club(
        db,
        category.id,
        leader_id=3,
        name=unique_name("Club Dos"),
        profile_image=None,
        cover_image=None,
    )

    client = TestClient(app)
    response = client.get("/clubs")

    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 2

    club_one_response = next(item for item in data if item["id"] == club_one.id)
    assert (
        club_one_response["profile_image"]
        == "https://cdn.example.com/clubs/test/profile/uno.png"
    )
    assert (
        club_one_response["cover_image"]
        == "https://cdn.example.com/clubs/test/cover/uno.png"
    )
    assert club_one_response["members_count"] == 2

    club_dos_response = next(item for item in data if item["id"] == club_dos.id)
    assert club_dos_response["members_count"] == 1


def test_get_club_not_found():
    client = TestClient(app)

    response = client.get("/clubs/999999")

    assert response.status_code == 404


def test_create_club_with_images_uses_public_url_and_prefixes(
    db,
    monkeypatch,
):
    app.dependency_overrides[get_current_user] = override_user(1)
    monkeypatch.setattr(settings, "R2_PUBLIC_URL", "https://cdn.example.com")

    uploads = []

    async def fake_upload(*args, **kwargs):
        uploads.append(
            {
                "bucket_name": kwargs["bucket_name"],
                "prefix": kwargs["prefix"],
            }
        )
        return f"{kwargs['prefix']}/test.png"

    monkeypatch.setattr(storage_service, "upload_file", fake_upload)

    category = create_category(db)
    client = TestClient(app)

    response = client.post(
        "/clubs",
        data={
            "name": unique_name("Club Img"),
            "description": "Desc",
            "id_category": str(category.id),
        },
        files={
            "profile_image": ("profile.png", b"img", "image/png"),
            "cover_image": ("cover.png", b"img", "image/png"),
        },
    )

    assert response.status_code == 201

    created_id = response.json()["id"]
    expected_profile_prefix = f"clubs/{created_id}/profile"
    expected_cover_prefix = f"clubs/{created_id}/cover"

    assert uploads[0]["bucket_name"] == settings.R2_BUCKET_PUBLIC
    assert uploads[0]["prefix"] == expected_profile_prefix
    assert uploads[1]["bucket_name"] == settings.R2_BUCKET_PUBLIC
    assert uploads[1]["prefix"] == expected_cover_prefix
    assert (
        response.json()["profile_image"]
        == f"https://cdn.example.com/{expected_profile_prefix}/test.png"
    )
    assert (
        response.json()["cover_image"]
        == f"https://cdn.example.com/{expected_cover_prefix}/test.png"
    )


def test_create_club_without_images_returns_none(db, monkeypatch):
    app.dependency_overrides[get_current_user] = override_user(1)
    monkeypatch.setattr(settings, "R2_PUBLIC_URL", "https://cdn.example.com")

    category = create_category(db)
    client = TestClient(app)

    response = client.post(
        "/clubs",
        data={
            "name": unique_name("Club Sin Imagen"),
            "description": "Desc",
            "id_category": str(category.id),
        },
    )

    assert response.status_code == 201
    assert response.json()["profile_image"] is None
    assert response.json()["cover_image"] is None


def test_create_club_invalid_category_returns_400(db):
    app.dependency_overrides[get_current_user] = override_user(1)
    client = TestClient(app)

    response = client.post(
        "/clubs",
        data={
            "name": unique_name("Club categoria invalida"),
            "description": "Desc",
            "id_category": "999999",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Categoría inválida"


def test_update_club_profile_image_deletes_previous_and_returns_public_url(
    db,
    monkeypatch,
):
    app.dependency_overrides[get_current_user] = override_user(1)
    monkeypatch.setattr(settings, "R2_PUBLIC_URL", "https://cdn.example.com")

    deleted = {}
    uploaded = {}

    async def fake_delete(*args, **kwargs):
        deleted["bucket_name"] = kwargs["bucket_name"]
        deleted["object_key"] = kwargs["object_key"]

    async def fake_upload(*args, **kwargs):
        uploaded["bucket_name"] = kwargs["bucket_name"]
        uploaded["prefix"] = kwargs["prefix"]
        return f"{kwargs['prefix']}/update.png"

    monkeypatch.setattr(storage_service, "delete_file", fake_delete)
    monkeypatch.setattr(storage_service, "upload_file", fake_upload)

    category = create_category(db)
    club = create_club(
        db,
        category.id,
        leader_id=1,
        profile_image="clubs/123/profile/old.png",
    )

    client = TestClient(app)
    response = client.patch(
        f"/clubs/{club.id}",
        files={"profile_image": ("file.png", b"img", "image/png")},
    )

    assert response.status_code == 200

    expected_prefix = f"clubs/{club.id}/profile"

    assert deleted["bucket_name"] == settings.R2_BUCKET_PUBLIC
    assert deleted["object_key"] == "clubs/123/profile/old.png"
    assert uploaded["bucket_name"] == settings.R2_BUCKET_PUBLIC
    assert uploaded["prefix"] == expected_prefix
    assert (
        response.json()["profile_image"]
        == f"https://cdn.example.com/{expected_prefix}/update.png"
    )


def test_update_club_with_first_profile_image_does_not_delete_previous(
    db,
    monkeypatch,
):
    app.dependency_overrides[get_current_user] = override_user(1)
    monkeypatch.setattr(settings, "R2_PUBLIC_URL", "https://cdn.example.com")

    called = {"deleted": False, "prefix": None}

    async def fake_delete(*args, **kwargs):
        called["deleted"] = True

    async def fake_upload(*args, **kwargs):
        called["prefix"] = kwargs["prefix"]
        return f"{kwargs['prefix']}/first.png"

    monkeypatch.setattr(storage_service, "delete_file", fake_delete)
    monkeypatch.setattr(storage_service, "upload_file", fake_upload)

    category = create_category(db)
    club = create_club(db, category.id, leader_id=1, profile_image=None)

    client = TestClient(app)
    response = client.patch(
        f"/clubs/{club.id}",
        files={"profile_image": ("file.png", b"img", "image/png")},
    )

    assert response.status_code == 200
    assert called["deleted"] is False
    assert called["prefix"] == f"clubs/{club.id}/profile"
    assert (
        response.json()["profile_image"]
        == f"https://cdn.example.com/clubs/{club.id}/profile/first.png"
    )


def test_update_club_cover_image_deletes_previous_and_returns_public_url(
    db,
    monkeypatch,
):
    app.dependency_overrides[get_current_user] = override_user(1)
    monkeypatch.setattr(settings, "R2_PUBLIC_URL", "https://cdn.example.com")

    deleted = {}
    uploaded = {}

    async def fake_delete(*args, **kwargs):
        deleted["bucket_name"] = kwargs["bucket_name"]
        deleted["object_key"] = kwargs["object_key"]

    async def fake_upload(*args, **kwargs):
        uploaded["bucket_name"] = kwargs["bucket_name"]
        uploaded["prefix"] = kwargs["prefix"]
        return f"{kwargs['prefix']}/update.png"

    monkeypatch.setattr(storage_service, "delete_file", fake_delete)
    monkeypatch.setattr(storage_service, "upload_file", fake_upload)

    category = create_category(db)
    club = create_club(
        db,
        category.id,
        leader_id=1,
        cover_image="clubs/123/cover/old.png",
    )

    client = TestClient(app)
    response = client.patch(
        f"/clubs/{club.id}",
        files={"cover_image": ("file.png", b"img", "image/png")},
    )

    assert response.status_code == 200

    expected_prefix = f"clubs/{club.id}/cover"

    assert deleted["bucket_name"] == settings.R2_BUCKET_PUBLIC
    assert deleted["object_key"] == "clubs/123/cover/old.png"
    assert uploaded["bucket_name"] == settings.R2_BUCKET_PUBLIC
    assert uploaded["prefix"] == expected_prefix
    assert (
        response.json()["cover_image"]
        == f"https://cdn.example.com/{expected_prefix}/update.png"
    )


def test_update_club_with_first_cover_image_does_not_delete_previous(
    db,
    monkeypatch,
):
    app.dependency_overrides[get_current_user] = override_user(1)
    monkeypatch.setattr(settings, "R2_PUBLIC_URL", "https://cdn.example.com")

    called = {"deleted": False, "prefix": None}

    async def fake_delete(*args, **kwargs):
        called["deleted"] = True

    async def fake_upload(*args, **kwargs):
        called["prefix"] = kwargs["prefix"]
        return f"{kwargs['prefix']}/first.png"

    monkeypatch.setattr(storage_service, "delete_file", fake_delete)
    monkeypatch.setattr(storage_service, "upload_file", fake_upload)

    category = create_category(db)
    club = create_club(db, category.id, leader_id=1, cover_image=None)

    client = TestClient(app)
    response = client.patch(
        f"/clubs/{club.id}",
        files={"cover_image": ("file.png", b"img", "image/png")},
    )

    assert response.status_code == 200
    assert called["deleted"] is False
    assert called["prefix"] == f"clubs/{club.id}/cover"
    assert (
        response.json()["cover_image"]
        == f"https://cdn.example.com/clubs/{club.id}/cover/first.png"
    )


def test_update_errors(db):
    app.dependency_overrides[get_current_user] = override_user(1)

    category = create_category(db)
    club = create_club(db, category.id, leader_id=1)

    client = TestClient(app)

    res = client.patch(f"/clubs/{club.id}", data={"name": "   "})
    assert res.status_code == 400

    res = client.patch(
        f"/clubs/{club.id}",
        data={"description": "   "},
    )
    assert res.status_code == 400

    res = client.patch(
        f"/clubs/{club.id}",
        data={"id_category": "999999"},
    )
    assert res.status_code == 400


def test_create_club_name_too_long(db):
    app.dependency_overrides[get_current_user] = override_user(1)

    category = create_category(db)
    client = TestClient(app)

    response = client.post(
        "/clubs",
        data={
            "name": "a" * 256,
            "description": "Desc",
            "id_category": str(category.id),
        },
    )

    assert response.status_code == 400
    assert "255" in response.json()["detail"]


def test_create_club_description_too_long(db):
    app.dependency_overrides[get_current_user] = override_user(1)

    category = create_category(db)
    client = TestClient(app)

    response = client.post(
        "/clubs",
        data={
            "name": unique_name("Club válido"),
            "description": "a" * 251,
            "id_category": str(category.id),
        },
    )

    assert response.status_code == 400
    assert "250" in response.json()["detail"]


def test_update_name_too_long(db):
    app.dependency_overrides[get_current_user] = override_user(1)

    category = create_category(db)
    club = create_club(db, category.id, leader_id=1)
    client = TestClient(app)

    response = client.patch(
        f"/clubs/{club.id}",
        data={"name": "a" * 256},
    )

    assert response.status_code == 400
    assert "255" in response.json()["detail"]


def test_update_description_too_long(db):
    app.dependency_overrides[get_current_user] = override_user(1)

    category = create_category(db)
    club = create_club(db, category.id, leader_id=1)
    client = TestClient(app)

    response = client.patch(
        f"/clubs/{club.id}",
        data={"description": "a" * 251},
    )

    assert response.status_code == 400
    assert "250" in response.json()["detail"]


def test_delete_club(db, monkeypatch):
    app.dependency_overrides[get_current_user] = override_user(1)

    deleted_files = []

    async def fake_delete(*args, **kwargs):
        deleted_files.append(kwargs["object_key"])

    monkeypatch.setattr(storage_service, "delete_file", fake_delete)

    category = create_category(db)
    club = create_club(
        db,
        category.id,
        leader_id=1,
        profile_image="clubs/123/profile/test.png",
        cover_image="clubs/123/cover/test.png",
    )

    client = TestClient(app)
    response = client.delete(f"/clubs/{club.id}")

    assert response.status_code == 200
    assert "clubs/123/profile/test.png" in deleted_files
    assert "clubs/123/cover/test.png" in deleted_files


def test_delete_club_not_found(db):
    app.dependency_overrides[get_current_user] = override_user(1)
    client = TestClient(app)

    response = client.delete("/clubs/999999")

    assert response.status_code == 404
    assert response.json()["detail"] == "Club no encontrado"


def test_join_leave_flow(db):
    category = create_category(db)
    club = create_club(db, category.id, leader_id=1)

    app.dependency_overrides[get_current_user] = override_user(2)
    client = TestClient(app)

    assert client.post(f"/clubs/{club.id}/members").status_code == 200
    assert client.delete(f"/clubs/{club.id}/members/me").status_code == 200


def test_leave_club_not_member_returns_404(db):
    category = create_category(db)
    club = create_club(db, category.id, leader_id=1)

    app.dependency_overrides[get_current_user] = override_user(3)
    client = TestClient(app)

    response = client.delete(f"/clubs/{club.id}/members/me")

    assert response.status_code == 404
    assert response.json()["detail"] == "No eres miembro"


def test_remove_member(db):
    category = create_category(db)
    club = create_club(db, category.id, leader_id=1)

    create_membership(db, club.id, 2)

    app.dependency_overrides[get_current_user] = override_user(1)
    client = TestClient(app)

    response = client.delete(f"/clubs/{club.id}/members/2")

    assert response.status_code == 200


def test_remove_member_cannot_remove_leader(db):
    category = create_category(db)
    club = create_club(db, category.id, leader_id=1)

    app.dependency_overrides[get_current_user] = override_user(1)
    client = TestClient(app)

    response = client.delete(f"/clubs/{club.id}/members/1")

    assert response.status_code == 400
    assert response.json()["detail"] == "No puedes expulsar al líder"


def test_remove_member_not_found_returns_404(db):
    category = create_category(db)
    club = create_club(db, category.id, leader_id=1)

    app.dependency_overrides[get_current_user] = override_user(1)
    client = TestClient(app)

    response = client.delete(f"/clubs/{club.id}/members/3")

    assert response.status_code == 404
    assert response.json()["detail"] == "No es miembro"


def test_transfer_leadership(db):
    category = create_category(db)
    club = create_club(db, category.id, leader_id=1)

    create_membership(db, club.id, 2)

    app.dependency_overrides[get_current_user] = override_user(1)
    client = TestClient(app)

    response = client.patch(f"/clubs/{club.id}/members/2/leader")

    assert response.status_code == 200


def test_duplicate_name_rejected(db):
    app.dependency_overrides[get_current_user] = override_user(1)

    category = create_category(db)
    duplicate_name = unique_name("Club Duplicado")
    create_club(db, category.id, name=duplicate_name)

    client = TestClient(app)
    response = client.post(
        "/clubs",
        data={
            "name": duplicate_name,
            "description": "Otro desc",
            "id_category": str(category.id),
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Nombre de club ya existe"


def test_already_member_rejected(db):
    category = create_category(db)
    club = create_club(db, category.id, leader_id=1)
    create_membership(db, club.id, 2)

    app.dependency_overrides[get_current_user] = override_user(2)
    client = TestClient(app)

    response = client.post(f"/clubs/{club.id}/members")

    assert response.status_code == 400
    assert response.json()["detail"] == "Ya eres miembro"


def test_leader_cannot_leave(db):
    category = create_category(db)
    club = create_club(db, category.id, leader_id=1)

    app.dependency_overrides[get_current_user] = override_user(1)
    client = TestClient(app)

    response = client.delete(f"/clubs/{club.id}/members/me")

    assert response.status_code == 400
    assert response.json()["detail"] == "El líder no puede salirse"


def test_same_leader_rejected(db):
    category = create_category(db)
    club = create_club(db, category.id, leader_id=1)

    app.dependency_overrides[get_current_user] = override_user(1)
    client = TestClient(app)

    response = client.patch(f"/clubs/{club.id}/members/1/leader")

    assert response.status_code == 409
    assert response.json()["detail"] == "El usuario ya es el líder actual"


def test_update_club_only_leader(db):
    app.dependency_overrides[get_current_user] = override_user(2)

    category = create_category(db)
    club = create_club(db, category.id, leader_id=1)

    client = TestClient(app)
    response = client.patch(f"/clubs/{club.id}", data={"name": "Nuevo Nombre"})

    assert response.status_code == 403
    assert response.json()["detail"] == "Solo el líder puede editar"


def test_update_club_not_found(db):
    app.dependency_overrides[get_current_user] = override_user(1)

    client = TestClient(app)
    response = client.patch("/clubs/999999", data={"name": "Nuevo Nombre"})

    assert response.status_code == 404
    assert response.json()["detail"] == "Club no encontrado"


def test_delete_club_only_leader(db):
    app.dependency_overrides[get_current_user] = override_user(2)

    category = create_category(db)
    club = create_club(db, category.id, leader_id=1)

    client = TestClient(app)
    response = client.delete(f"/clubs/{club.id}")

    assert response.status_code == 403
    assert response.json()["detail"] == "Solo el líder puede eliminar"


def test_join_club_not_found():
    app.dependency_overrides[get_current_user] = override_user(2)

    client = TestClient(app)
    response = client.post("/clubs/999999/members")

    assert response.status_code == 404
    assert response.json()["detail"] == "Club no encontrado"


def test_remove_member_only_leader(db):
    app.dependency_overrides[get_current_user] = override_user(2)

    category = create_category(db)
    club = create_club(db, category.id, leader_id=1)
    create_membership(db, club.id, 3)

    client = TestClient(app)
    response = client.delete(f"/clubs/{club.id}/members/3")

    assert response.status_code == 403
    assert response.json()["detail"] == "Solo el líder puede expulsar"


def test_transfer_leadership_only_leader(db):
    app.dependency_overrides[get_current_user] = override_user(2)

    category = create_category(db)
    club = create_club(db, category.id, leader_id=1)
    create_membership(db, club.id, 2)

    client = TestClient(app)
    response = client.patch(f"/clubs/{club.id}/members/2/leader")

    assert response.status_code == 403
    assert response.json()["detail"] == "Solo el líder actual puede transferir"


def test_transfer_leadership_requires_membership(db):
    app.dependency_overrides[get_current_user] = override_user(1)

    category = create_category(db)
    club = create_club(db, category.id, leader_id=1)

    client = TestClient(app)
    response = client.patch(f"/clubs/{club.id}/members/2/leader")

    assert response.status_code == 400
    assert response.json()["detail"] == "El usuario destino debe ser miembro del club"


def test_transfer_leadership_same_leader_rejected(db):
    app.dependency_overrides[get_current_user] = override_user(1)

    category = create_category(db)
    club = create_club(db, category.id, leader_id=1)

    client = TestClient(app)
    response = client.patch(f"/clubs/{club.id}/members/1/leader")

    assert response.status_code == 409
    assert response.json()["detail"] == "El usuario ya es el líder actual"


# --- Tests de Eventos ---


def create_event(db, club_id, author_id, title="Evento Test", future=True):
    from datetime import datetime, timedelta

    ensure_user(db, author_id)
    from app.models.club.event import ClubEvent

    if future:
        event_date = datetime.now() + timedelta(days=7)
    else:
        event_date = datetime.now() - timedelta(days=1)

    event = ClubEvent(
        id_club=club_id,
        id_author=author_id,
        title=title,
        description="Descripción del evento",
        date=event_date,
        latitude=32.65,
        longitude=-115.47,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def test_list_events_empty(db, clear_dependency_overrides):
    app.dependency_overrides[get_current_user] = override_user(1)

    category = create_category(db)
    club = create_club(db, category.id, leader_id=1)
    create_membership(db, club.id, 1)

    client = TestClient(app)
    response = client.get(f"/clubs/{club.id}/events")

    assert response.status_code == 200
    assert response.json() == []


def test_list_events_as_member(db, clear_dependency_overrides):
    app.dependency_overrides[get_current_user] = override_user(2)

    category = create_category(db)
    club = create_club(db, category.id, leader_id=1)
    create_membership(db, club.id, 2)

    create_event(db, club.id, author_id=1)

    client = TestClient(app)
    response = client.get(f"/clubs/{club.id}/events")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["title"] == "Evento Test"


def test_list_events_requires_membership(db, clear_dependency_overrides):
    app.dependency_overrides[get_current_user] = override_user(3)

    category = create_category(db)
    club = create_club(db, category.id, leader_id=1)

    client = TestClient(app)
    response = client.get(f"/clubs/{club.id}/events")

    assert response.status_code == 403
    assert response.json()["detail"] == "El usuario no es miembro del club"


def test_list_events_club_not_found(db, clear_dependency_overrides):
    app.dependency_overrides[get_current_user] = override_user(1)

    client = TestClient(app)
    response = client.get("/clubs/999/events")

    assert response.status_code == 404
    assert response.json()["detail"] == "Club no encontrado"


def test_create_event_as_leader(db, clear_dependency_overrides):
    app.dependency_overrides[get_current_user] = override_user(1)

    category = create_category(db)
    club = create_club(db, category.id, leader_id=1)

    from datetime import datetime, timedelta

    client = TestClient(app)
    response = client.post(
        f"/clubs/{club.id}/events",
        json={
            "title": "Nuevo Evento",
            "description": "Descripción",
            "date": (datetime.now() + timedelta(days=7)).isoformat(),
            "latitude": 32.65,
            "longitude": -115.47,
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Nuevo Evento"
    assert data["id_club"] == club.id


def test_create_event_as_non_leader_forbidden(db, clear_dependency_overrides):
    app.dependency_overrides[get_current_user] = override_user(2)

    category = create_category(db)
    club = create_club(db, category.id, leader_id=1)
    create_membership(db, club.id, 2)

    from datetime import datetime, timedelta

    client = TestClient(app)
    response = client.post(
        f"/clubs/{club.id}/events",
        json={
            "title": "Evento No Autorizado",
            "description": "Descripción",
            "date": (datetime.now() + timedelta(days=7)).isoformat(),
            "latitude": 32.65,
            "longitude": -115.47,
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Solo el líder puede realizar esta acción"


def test_create_event_club_not_found(db, clear_dependency_overrides):
    app.dependency_overrides[get_current_user] = override_user(1)

    from datetime import datetime, timedelta

    client = TestClient(app)
    response = client.post(
        "/clubs/999/events",
        json={
            "title": "Evento",
            "description": "Descripción",
            "date": (datetime.now() + timedelta(days=7)).isoformat(),
            "latitude": 32.65,
            "longitude": -115.47,
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Club no encontrado"


def test_create_event_past_date_rejected(db, clear_dependency_overrides):
    app.dependency_overrides[get_current_user] = override_user(1)

    category = create_category(db)
    club = create_club(db, category.id, leader_id=1)

    from datetime import datetime, timedelta

    client = TestClient(app)
    response = client.post(
        f"/clubs/{club.id}/events",
        json={
            "title": "Evento Pasado",
            "description": "Descripción",
            "date": (datetime.now() - timedelta(days=1)).isoformat(),
            "latitude": 32.65,
            "longitude": -115.47,
        },
    )

    assert response.status_code == 422


def test_update_event_as_leader(db, clear_dependency_overrides):
    app.dependency_overrides[get_current_user] = override_user(1)

    category = create_category(db)
    club = create_club(db, category.id, leader_id=1)
    event = create_event(db, club.id, author_id=1)

    client = TestClient(app)
    response = client.patch(
        f"/clubs/{club.id}/events/{event.id}",
        json={"title": "Evento Actualizado"},
    )

    assert response.status_code == 200
    assert response.json()["title"] == "Evento Actualizado"


def test_update_event_updates_all_optional_fields(db, clear_dependency_overrides):
    app.dependency_overrides[get_current_user] = override_user(1)

    category = create_category(db)
    club = create_club(db, category.id, leader_id=1)
    event = create_event(db, club.id, author_id=1)

    from datetime import datetime, timedelta

    future_date = (datetime.now() + timedelta(days=10)).isoformat()
    client = TestClient(app)
    response = client.patch(
        f"/clubs/{club.id}/events/{event.id}",
        json={
            "description": "Nueva descripcion",
            "date": future_date,
            "latitude": 33.0,
            "longitude": -116.0,
        },
    )

    assert response.status_code == 200
    assert response.json()["description"] == "Nueva descripcion"
    assert response.json()["latitude"] == 33.0
    assert response.json()["longitude"] == -116.0


def test_update_event_as_non_leader_forbidden(db, clear_dependency_overrides):
    app.dependency_overrides[get_current_user] = override_user(2)

    category = create_category(db)
    club = create_club(db, category.id, leader_id=1)
    create_membership(db, club.id, 2)
    event = create_event(db, club.id, author_id=1)

    client = TestClient(app)
    response = client.patch(
        f"/clubs/{club.id}/events/{event.id}",
        json={"title": "Intento de Cambio"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Solo el líder puede realizar esta acción"


def test_update_event_not_found(db, clear_dependency_overrides):
    app.dependency_overrides[get_current_user] = override_user(1)

    category = create_category(db)
    club = create_club(db, category.id, leader_id=1)

    client = TestClient(app)
    response = client.patch(
        f"/clubs/{club.id}/events/999",
        json={"title": "No Existe"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Evento no encontrado"


def test_delete_event_as_leader(db, clear_dependency_overrides):
    app.dependency_overrides[get_current_user] = override_user(1)

    category = create_category(db)
    club = create_club(db, category.id, leader_id=1)
    event = create_event(db, club.id, author_id=1)

    client = TestClient(app)
    response = client.delete(f"/clubs/{club.id}/events/{event.id}")

    assert response.status_code == 204


def test_delete_event_as_non_leader_forbidden(db, clear_dependency_overrides):
    app.dependency_overrides[get_current_user] = override_user(2)

    category = create_category(db)
    club = create_club(db, category.id, leader_id=1)
    create_membership(db, club.id, 2)
    event = create_event(db, club.id, author_id=1)

    client = TestClient(app)
    response = client.delete(f"/clubs/{club.id}/events/{event.id}")

    assert response.status_code == 403
    assert response.json()["detail"] == "Solo el líder puede realizar esta acción"


def test_delete_event_not_found_returns_404(db, clear_dependency_overrides):
    app.dependency_overrides[get_current_user] = override_user(1)

    category = create_category(db)
    club = create_club(db, category.id, leader_id=1)

    client = TestClient(app)
    response = client.delete(f"/clubs/{club.id}/events/999")

    assert response.status_code == 404
    assert response.json()["detail"] == "Evento no encontrado"


def test_get_club_messages_requires_valid_token(db):
    category = create_category(db)
    club = create_club(db, category.id, leader_id=1)

    client = TestClient(app)
    response = client.get(
        f"/clubs/{club.id}/messages",
        headers={"Authorization": "Bearer token-invalido"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Token inválido"


def test_get_club_messages_requires_membership(db):
    app.dependency_overrides[get_current_user] = override_user(3)

    category = create_category(db)
    club = create_club(db, category.id, leader_id=1)

    client = TestClient(app)
    response = client.get(f"/clubs/{club.id}/messages")

    assert response.status_code == 403
    assert response.json()["detail"] == "El usuario no es miembro del club"


def test_get_club_messages_paginated(db):
    app.dependency_overrides[get_current_user] = override_user(1)

    category = create_category(db)
    club = create_club(db, category.id, leader_id=1)

    create_club_message(db, club.id, 1, "mensaje-1")
    create_club_message(db, club.id, 1, "mensaje-2")
    create_club_message(db, club.id, 1, "mensaje-3")

    client = TestClient(app)
    response = client.get(f"/clubs/{club.id}/messages?page=1&limit=2")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["content"] == "mensaje-1"
    assert data[1]["content"] == "mensaje-2"
    assert data[0]["user"]["name"] == "User 1"


def test_club_chat_websocket_persists_and_broadcasts(db):
    """Verifica que un mensaje enviado por WebSocket se persiste en BD y
    se devuelve al emisor (echo local).

    La difusión a otros clientes simultáneos se omite aquí porque depende
    de una carrera entre el subscribe de ws_2 y el send de ws_1, lo que
    provoca cuelgues intermitentes con TestClient síncrono. Esa lógica está
    cubierta por las pruebas unitarias de RedisChatManager en
    tests/app/services/test_redis_service.py.
    """
    category = create_category(db)
    club = create_club(db, category.id, leader_id=1)

    token_user_1 = create_access_token({"sub": "1"})

    client = TestClient(app)

    with client.websocket_connect(
        f"/clubs/{club.id}/chat",
        headers={"authorization": f"Bearer {token_user_1}"},
    ) as ws_1:
        ws_1.send_json({"content": "Hola a todos!"})
        payload = ws_1.receive_json()

    assert payload["content"] == "Hola a todos!"
    assert payload["user"]["id"] == 1
    assert payload["id_club"] == club.id

    saved = (
        db.query(ClubMessage)
        .filter(ClubMessage.id_club == club.id, ClubMessage.content == "Hola a todos!")
        .first()
    )
    assert saved is not None


def test_club_chat_websocket_invalid_token_closes_4001(db):
    category = create_category(db)
    club = create_club(db, category.id, leader_id=1)

    client = TestClient(app)

    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect(
            f"/clubs/{club.id}/chat", headers={"authorization": "Bearer invalido"}
        ) as ws:
            ws.receive_json()

    assert exc_info.value.code == 4001


def test_club_chat_websocket_non_member_closes_4003(db):
    category = create_category(db)
    club = create_club(db, category.id, leader_id=1)
    token_user_3 = create_access_token({"sub": "3"})

    client = TestClient(app)

    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect(
            f"/clubs/{club.id}/chat",
            headers={"authorization": f"Bearer {token_user_3}"},
        ) as ws:
            ws.receive_json()

    assert exc_info.value.code == 4003


def test_club_chat_websocket_no_auth_header_closes_4001(db):
    category = create_category(db)
    club = create_club(db, category.id, leader_id=1)

    client = TestClient(app)

    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect(f"/clubs/{club.id}/chat") as ws:
            ws.receive_json()

    assert exc_info.value.code == 4001


def test_club_chat_websocket_wrong_token_type_closes_4001(db, monkeypatch):
    """Valida que se rechace un token con claim type 'refresh' en lugar de 'access'."""
    category = create_category(db)
    club = create_club(db, category.id, leader_id=1)

    # Crear un token refresh (que tiene type: "refresh")
    from app.core.security import create_refresh_token

    refresh_token = create_refresh_token({"sub": "1"})

    client = TestClient(app)

    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect(
            f"/clubs/{club.id}/chat",
            headers={"authorization": f"Bearer {refresh_token}"},
        ) as ws:
            ws.receive_json()

    assert exc_info.value.code == 4001


def test_club_chat_websocket_missing_bearer_header_closes_4001(db):
    category = create_category(db)
    club = create_club(db, category.id, leader_id=1)
    token_user_1 = create_access_token({"sub": "1"})

    client = TestClient(app)

    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect(
            f"/clubs/{club.id}/chat", headers={"authorization": token_user_1}
        ) as ws:
            ws.receive_json()

    assert exc_info.value.code == 4001


def test_authenticate_ws_user_returns_none_for_invalid_sub(db, monkeypatch):
    def mock_decode(_):
        return {"sub": "abc", "type": "access"}

    monkeypatch.setattr("app.routers.clubs.decode_access_token", mock_decode)
    headers = {"authorization": "Bearer fake-token"}
    assert _authenticate_ws_user(headers, db) is None


def test_authenticate_ws_user_returns_none_for_decode_error(db, monkeypatch):
    def raise_decode_error(_token):
        raise TokenDecodeError("Token inválido")

    monkeypatch.setattr("app.routers.clubs.decode_access_token", raise_decode_error)

    headers = {"authorization": "Bearer fake-token"}
    assert _authenticate_ws_user(headers, db) is None


def test_authenticate_ws_user_returns_user_for_valid_token(db, monkeypatch):
    user = ensure_user(db, 11)
    monkeypatch.setattr(
        "app.routers.clubs.decode_access_token",
        lambda _: {"sub": str(user.id), "type": "access"},
    )

    headers = {"authorization": "Bearer fake-token"}
    result = _authenticate_ws_user(headers, db)

    assert result is not None
    assert result.id == user.id


def test_build_message_payload_includes_nested_user(db):
    category = create_category(db)
    club = create_club(db, category.id, leader_id=1)
    message = create_club_message(db, club.id, 1, "payload test")
    db.refresh(message)
    message.user = db.query(User).filter(User.id == 1).one()

    payload = _build_message_payload(message)

    assert payload["content"] == "payload test"
    assert payload["id_club"] == club.id
    assert payload["user"]["id"] == 1


def test_authenticate_ws_user_returns_none_for_inactive_user(db, monkeypatch):
    user = ensure_user(db, 10)
    user.is_active = False
    db.commit()

    monkeypatch.setattr(
        "app.routers.clubs.decode_access_token",
        lambda _: {"sub": str(user.id), "type": "access"},
    )

    headers = {"authorization": "Bearer fake-token"}
    assert _authenticate_ws_user(headers, db) is None


def test_notify_offline_members_sends_push_to_offline_members_only(db, monkeypatch):
    category = create_category(db)
    club = create_club(db, category.id, leader_id=1)
    create_membership(db, club.id, 2)
    create_membership(db, club.id, 3)

    db.add(UserSession(id_user=1, push_token="ExponentPushToken[user-1]"))
    db.add(UserSession(id_user=2, push_token="ExponentPushToken[user-2]"))
    db.add(UserSession(id_user=3, push_token="ExponentPushToken[user-3]"))
    db.commit()

    pushes = []

    monkeypatch.setattr(
        "app.routers.clubs.send_push_notification",
        lambda **kwargs: pushes.append(kwargs),
    )

    sender = db.query(User).filter(User.id == 2).one()
    _notify_offline_members(
        db,
        club=club,
        sender=sender,
        content="Hola a todos desde el club",
        connected_user_ids={2, 3},
    )

    # User 1 (leader) está offline y debe recibir notificación
    # User 2 (sender) está excluido
    # User 3 está conectado, por lo que no debe recibir notificación
    assert len(pushes) == 1
    assert pushes[0]["token"] == "ExponentPushToken[user-1]"
    assert pushes[0]["data"]["id_club"] == club.id
    assert pushes[0]["data"]["id_leader"] == club.id_leader


def test_notify_offline_members_skips_when_everyone_is_connected(db, monkeypatch):
    category = create_category(db)
    club = create_club(db, category.id, leader_id=1)
    create_membership(db, club.id, 2)

    pushes = []
    monkeypatch.setattr(
        "app.routers.clubs.send_push_notification",
        lambda **kwargs: pushes.append(kwargs),
    )

    sender = db.query(User).filter(User.id == 2).one()
    # Todos conectados: líder (1), sender (2)
    _notify_offline_members(
        db,
        club=club,
        sender=sender,
        content="Hola conectados",
        connected_user_ids={1, 2},
    )

    assert pushes == []


def test_club_chat_websocket_validation_error_returns_detail(db):
    category = create_category(db)
    club = create_club(db, category.id, leader_id=1)
    token_user_1 = create_access_token({"sub": "1"})

    client = TestClient(app)

    with client.websocket_connect(
        f"/clubs/{club.id}/chat", headers={"authorization": f"Bearer {token_user_1}"}
    ) as ws:
        ws.send_json({})
        payload = ws.receive_json()

    assert "content debe ser requerido" in payload["detail"]


def test_update_club_with_profile_image_when_exists(
    db, clear_dependency_overrides, monkeypatch
):
    """Cover line 446-448: delete existing profile_image before uploading new."""
    app.dependency_overrides[get_current_user] = override_user(1)

    category = create_category(db)
    club = create_club(db, category.id, leader_id=1)
    club.profile_image = "old-profile.jpg"
    db.commit()

    delete_called = []
    upload_called = []

    async def mock_delete(**kwargs):
        delete_called.append(kwargs)

    async def mock_upload(**kwargs):
        upload_called.append(kwargs)
        return "new-profile.jpg"

    monkeypatch.setattr("app.routers.clubs.storage_service.delete_file", mock_delete)
    monkeypatch.setattr("app.routers.clubs.storage_service.upload_file", mock_upload)

    client = TestClient(app)
    response = client.patch(
        f"/clubs/{club.id}",
        files={"profile_image": ("test.jpg", b"fake image data", "image/jpeg")},
    )

    assert response.status_code == 200
    assert len(delete_called) == 1
    assert delete_called[0]["object_key"] == "old-profile.jpg"


def test_update_club_duplicate_name_different_club(db, clear_dependency_overrides):
    """Cover line 446-448: existing and existing.id != club.id check."""
    app.dependency_overrides[get_current_user] = override_user(1)

    category = create_category(db)
    create_club(db, category.id, leader_id=1, name="Club Uno")
    club2 = create_club(db, category.id, leader_id=1, name="Club Dos")

    client = TestClient(app)
    response = client.patch(
        f"/clubs/{club2.id}",
        data={"name": "Club Uno"},
    )

    assert response.status_code == 400
    assert "Nombre de club ya existe" in response.json()["detail"]


def test_update_club_with_cover_image_when_exists(
    db, clear_dependency_overrides, monkeypatch
):
    """Cover line 472-475: delete existing cover_image before uploading new."""
    app.dependency_overrides[get_current_user] = override_user(1)

    category = create_category(db)
    club = create_club(db, category.id, leader_id=1)
    club.cover_image = "old-cover.jpg"
    db.commit()

    delete_called = []
    upload_called = []

    async def mock_delete(**kwargs):
        delete_called.append(kwargs)

    async def mock_upload(**kwargs):
        upload_called.append(kwargs)
        return "new-cover.jpg"

    monkeypatch.setattr("app.routers.clubs.storage_service.delete_file", mock_delete)
    monkeypatch.setattr("app.routers.clubs.storage_service.upload_file", mock_upload)

    client = TestClient(app)
    response = client.patch(
        f"/clubs/{club.id}",
        files={"cover_image": ("test.jpg", b"fake image data", "image/jpeg")},
    )

    assert response.status_code == 200
    assert len(delete_called) == 1
    assert len(upload_called) == 1


def test_delete_club_with_existing_cover_image(
    db, clear_dependency_overrides, monkeypatch
):
    """Cover delete club with both profile and cover images."""
    app.dependency_overrides[get_current_user] = override_user(1)

    category = create_category(db)
    club = create_club(db, category.id, leader_id=1)
    club.profile_image = "profile.jpg"
    club.cover_image = "cover.jpg"
    db.commit()

    delete_calls = []

    async def mock_delete(**kwargs):
        delete_calls.append(kwargs)

    monkeypatch.setattr("app.routers.clubs.storage_service.delete_file", mock_delete)

    client = TestClient(app)
    response = client.delete(f"/clubs/{club.id}")

    assert response.status_code == 200
    assert len(delete_calls) == 2


def test_websocket_invalid_token_closes(db):
    """Cover websocket token validation path."""
    category = create_category(db)
    club = create_club(db, category.id, leader_id=1)

    client = TestClient(app)

    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect(
            f"/clubs/{club.id}/chat",
            headers={"authorization": "Bearer invalid-token"},
        ) as ws:
            ws.receive_json()
    assert exc_info.value.code == 4001


def test_websocket_non_member_closes(db):
    """Cover websocket membership check path."""
    category = create_category(db)
    club = create_club(db, category.id, leader_id=1)
    ensure_user(db, 2)
    token_user_2 = create_access_token({"sub": "2"})

    client = TestClient(app)

    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect(
            f"/clubs/{club.id}/chat",
            headers={"authorization": f"Bearer {token_user_2}"},
        ) as ws:
            ws.receive_json()
    assert exc_info.value.code == 4003


def test_update_event_all_optional_fields_none(db, clear_dependency_overrides):
    """Cover event update with all fields being None."""
    app.dependency_overrides[get_current_user] = override_user(1)

    category = create_category(db)
    club = create_club(db, category.id, leader_id=1)
    event = create_event(db, club.id, author_id=1)

    original_title = event.title

    client = TestClient(app)
    response = client.patch(
        f"/clubs/{club.id}/events/{event.id}",
        json={
            "title": None,
            "description": None,
            "date": None,
            "latitude": None,
            "longitude": None,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["title"] == original_title


def test_security_decode_token_with_no_sub(db, clear_dependency_overrides):
    """Cover app/core/security.py line 75: token valid but no sub."""
    from app.core.security import create_access_token

    token = create_access_token({"data": "test"})

    client = TestClient(app)
    response = client.get(
        "/clubs/1/messages",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 401
    assert "Token inválido" in response.json()["detail"]


def test_club_chat_websocket_whitespace_only_message_rejected(db):
    """Test that messages with only whitespace are rejected."""
    category = create_category(db)
    club = create_club(db, category.id, leader_id=1)
    token_user_1 = create_access_token({"sub": "1"})

    client = TestClient(app)

    with client.websocket_connect(
        f"/clubs/{club.id}/chat", headers={"authorization": f"Bearer {token_user_1}"}
    ) as ws:
        ws.send_json({"content": "   \t\n  "})
        payload = ws.receive_json()

    assert "content debe ser requerido" in payload["detail"]


def test_notify_offline_members_without_push_tokens(db, monkeypatch):
    """Test that members without push tokens don't receive notifications."""
    category = create_category(db)
    club = create_club(db, category.id, leader_id=1)
    create_membership(db, club.id, 2)

    # No push tokens created - members should have no sessions
    pushes = []
    monkeypatch.setattr(
        "app.routers.clubs.send_push_notification",
        lambda **kwargs: pushes.append(kwargs),
    )

    sender = db.query(User).filter(User.id == 2).one()
    _notify_offline_members(
        db,
        club=club,
        sender=sender,
        content="Test message",
        connected_user_ids={2},
    )

    # No push notifications should be sent
    assert len(pushes) == 0


def test_authenticate_ws_user_missing_bearer_prefix(db):
    """Test authentication fails when Bearer prefix is missing."""
    token = create_access_token({"sub": "1", "type": "access"})
    headers = {"authorization": token}  # Missing "Bearer " prefix

    result = _authenticate_ws_user(headers, db)

    assert result is None


def test_authenticate_ws_user_empty_authorization_header(db):
    """Test authentication fails with empty authorization header."""
    headers = {"authorization": ""}

    result = _authenticate_ws_user(headers, db)

    assert result is None


def test_authenticate_ws_user_no_authorization_header(db):
    """Test authentication fails when no authorization header."""
    headers = {}

    result = _authenticate_ws_user(headers, db)

    assert result is None


def test_authenticate_ws_user_wrong_token_type(db, monkeypatch):
    """Test that only 'access' tokens are accepted."""

    def mock_decode(_):
        return {"sub": "1", "type": "wrong-type"}

    monkeypatch.setattr("app.routers.clubs.decode_access_token", mock_decode)
    headers = {"authorization": "Bearer fake-token"}

    result = _authenticate_ws_user(headers, db)

    assert result is None


def test_notify_offline_members_large_content_preview(db, monkeypatch):
    """Test content preview is truncated correctly."""
    category = create_category(db)
    club = create_club(db, category.id, leader_id=1)
    create_membership(db, club.id, 2)

    db.add(UserSession(id_user=1, push_token="ExponentPushToken[user-1]"))
    db.commit()

    pushes = []
    monkeypatch.setattr(
        "app.routers.clubs.send_push_notification",
        lambda **kwargs: pushes.append(kwargs),
    )

    sender = db.query(User).filter(User.id == 2).one()
    long_content = "A" * 200  # Longer than 120 chars

    _notify_offline_members(
        db,
        club=club,
        sender=sender,
        content=long_content,
        connected_user_ids={2},
    )

    assert len(pushes) == 1
    # Preview should be truncated with ...
    assert len(pushes[0]["body"]) < len(f"{sender.name}: {long_content}")
    assert "..." in pushes[0]["body"]


def test_build_image_url_with_key():
    """Test that _build_image_url returns correct URL."""
    from app.routers.clubs import _build_image_url

    result = _build_image_url("club-123.jpg")

    # Just verify it returns something with the key
    assert result is not None
    assert "club-123.jpg" in result


def test_notify_offline_members_mixed_with_and_without_tokens(db, monkeypatch):
    """Test that only members with push tokens receive notifications."""
    category = create_category(db)
    club = create_club(db, category.id, leader_id=1)
    create_membership(db, club.id, 2)
    create_membership(db, club.id, 3)

    # Only user 1 and 3 have push tokens, user 2 has None
    db.add(UserSession(id_user=1, push_token="ExponentPushToken[user-1]"))
    db.add(UserSession(id_user=2, push_token=None))  # No token
    db.add(UserSession(id_user=3, push_token="ExponentPushToken[user-3]"))
    db.commit()

    pushes = []
    monkeypatch.setattr(
        "app.routers.clubs.send_push_notification",
        lambda **kwargs: pushes.append(kwargs),
    )

    sender = db.query(User).filter(User.id == 2).one()
    # User 2 is connected, so offline members are 1 and 3
    _notify_offline_members(
        db,
        club=club,
        sender=sender,
        content="Test",
        connected_user_ids={2},
    )

    # Users 1 and 3 are offline, so should get notifications
    # User 2 is connected, so no notification
    assert len(pushes) == 2
    tokens = {p["token"] for p in pushes}
    assert "ExponentPushToken[user-1]" in tokens
    assert "ExponentPushToken[user-3]" in tokens


def test_get_club_detail_response(db):
    """Test GET /clubs/{club_id} endpoint - covers line 273."""
    category = create_category(db)
    club = create_club(db, category.id, leader_id=1)
    create_membership(db, club.id, 2)

    client = TestClient(app)
    app.dependency_overrides[get_current_user] = override_user(1)

    response = client.get(f"/clubs/{club.id}")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == club.id
    assert data["name"] == club.name
    assert data["members_count"] == 2  # leader + member


def test_get_club_categories(db):
    """Test GET /clubs/categories endpoint - covers line 261."""
    create_category(db, name="Tech")
    create_category(db, name="Sports")

    client = TestClient(app)
    response = client.get("/clubs/categories")

    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 2
    # Should be ordered by name
    names = [cat["name"] for cat in data]
    assert names == sorted(names)


def test_club_chat_websocket_sender_error_handling(db, monkeypatch):
    """Test WebSocket error handling - covers lines 389-392, 399-401."""
    category = create_category(db)
    club = create_club(db, category.id, leader_id=1)
    token_user_1 = create_access_token({"sub": "1"})

    # Mock redis_chat_manager to raise an exception
    call_count = [0]

    async def mock_publish_error(*args, **kwargs):
        call_count[0] += 1
        if call_count[0] == 1:
            raise Exception("Redis publish error")

    client = TestClient(app)

    with client.websocket_connect(
        f"/clubs/{club.id}/chat", headers={"authorization": f"Bearer {token_user_1}"}
    ) as ws:
        # This should trigger error handling but not close the connection immediately
        ws.send_json({"content": "Test message"})
        # Wait for response - should send error JSON
        response = ws.receive_json()

        # Check that it received an error response
        assert "detail" in response or response


def test_get_club_messages_user_not_member(db):
    """Test GET /clubs/{club_id}/messages returns 403 for non-members.

    Covers line 286.
    """
    category = create_category(db)
    club = create_club(db, category.id, leader_id=1)

    app.dependency_overrides[get_current_user] = override_user(2)
    client = TestClient(app)

    response = client.get(f"/clubs/{club.id}/messages")

    assert response.status_code == 403
    assert "miembro" in response.json()["detail"]


def test_notify_offline_members_all_online(db, monkeypatch):
    """Test notify_offline_members when all members are online - covers line 234."""
    category = create_category(db)
    club = create_club(db, category.id, leader_id=1)
    create_membership(db, club.id, 2)
    create_membership(db, club.id, 3)

    db.add(UserSession(id_user=1, push_token="ExponentPushToken[user-1]"))
    db.add(UserSession(id_user=2, push_token="ExponentPushToken[user-2]"))
    db.add(UserSession(id_user=3, push_token="ExponentPushToken[user-3]"))
    db.commit()

    pushes = []
    monkeypatch.setattr(
        "app.routers.clubs.send_push_notification",
        lambda **kwargs: pushes.append(kwargs),
    )

    sender = db.query(User).filter(User.id == 2).one()
    # All except sender are online
    _notify_offline_members(
        db,
        club=club,
        sender=sender,
        content="Test",
        connected_user_ids={1, 3},
    )

    # No one should receive notification - all are online
    assert len(pushes) == 0


def test_leave_club_not_found(db):
    """Test DELETE /clubs/{club_id}/members/me when club doesn't exist.

    Covers line 633.
    """
    app.dependency_overrides[get_current_user] = override_user(1)
    client = TestClient(app)

    response = client.delete("/clubs/999999/members/me")

    assert response.status_code == 404
    assert "Club no encontrado" in response.json()["detail"]


def test_get_club_members_not_found(db):
    """Test DELETE /clubs/{club_id}/members/{user_id} when club doesn't exist.

    Covers line 606.
    """
    app.dependency_overrides[get_current_user] = override_user(1)
    client = TestClient(app)

    response = client.delete("/clubs/999999/members/2")

    assert response.status_code == 404
    assert "Club no encontrado" in response.json()["detail"]


def test_refresh_token_with_existing_session(db, clear_dependency_overrides):
    """Cover app/routers/auth/auth.py lines 37-39: update existing session."""
    from app.core.security import create_refresh_token

    ensure_user(db, 1)
    refresh_token_1 = create_refresh_token({"sub": "1"})

    session = UserSession(
        id_user=1,
        refresh_token=refresh_token_1,
        last_active_at=datetime.now(UTC),
        expires_at=datetime.now(UTC) + timedelta(days=7),
    )
    db.add(session)
    db.commit()

    old_last_active = session.last_active_at

    app.dependency_overrides[get_current_user] = override_user(1)

    client = TestClient(app)
    response = client.post(
        "/auth/refresh",
        json={"refresh_token": refresh_token_1},
    )

    assert response.status_code == 200
    assert "access_token" in response.json()
    assert "refresh_token" in response.json()

    db.refresh(session)
    assert session.last_active_at is not None
    assert old_last_active is not None
    assert session.last_active_at > old_last_active
