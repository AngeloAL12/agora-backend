import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.roles import RoleName
from app.core.security import get_current_user
from app.main import app
from app.models.auth.role import Role
from app.models.auth.user import User
from app.models.club.club import Club
from app.models.club.club_category import ClubCategory
from app.models.club.club_member import ClubMember
from app.schemas.auth.auth import CurrentUser
from app.services.storage_service import storage_service


@pytest.fixture(autouse=True)
def seed_users(db):
    ensure_user(db, 1)
    ensure_user(db, 2)
    ensure_user(db, 3)


@pytest.fixture(autouse=True)
def clear_overrides():
    yield
    app.dependency_overrides.pop(get_current_user, None)


def override_user(user_id=1):
    return lambda: CurrentUser(id=user_id, role=RoleName.USER)


def unique_name(prefix: str) -> str:
    return f"{prefix} {uuid.uuid4().hex[:8]}"


def ensure_user(db, user_id):
    role = db.query(Role).filter(Role.name == RoleName.USER.value).first()

    if not role:
        role = Role(name=RoleName.USER.value)
        db.add(role)
        db.commit()
        db.refresh(role)

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
    db.commit()
    db.refresh(club)

    existing_membership = (
        db.query(ClubMember)
        .filter(
            ClubMember.id_club == club.id,
            ClubMember.id_user == leader_id,
        )
        .first()
    )
    if not existing_membership:
        db.add(ClubMember(id_club=club.id, id_user=leader_id))
        db.commit()

    return club


def create_membership(db, club_id, user_id):
    ensure_user(db, user_id)

    exists = (
        db.query(ClubMember)
        .filter(
            ClubMember.id_club == club_id,
            ClubMember.id_user == user_id,
        )
        .first()
    )
    if not exists:
        db.add(ClubMember(id_club=club_id, id_user=user_id))
        db.commit()


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

    create_club(
        db,
        category.id,
        leader_id=2,
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


def test_join_leave_flow(db):
    category = create_category(db)
    club = create_club(db, category.id, leader_id=1)

    app.dependency_overrides[get_current_user] = override_user(2)
    client = TestClient(app)

    assert client.post(f"/clubs/{club.id}/members").status_code == 200
    assert client.delete(f"/clubs/{club.id}/members/me").status_code == 200


def test_remove_member(db):
    category = create_category(db)
    club = create_club(db, category.id, leader_id=1)

    create_membership(db, club.id, 2)

    app.dependency_overrides[get_current_user] = override_user(1)
    client = TestClient(app)

    response = client.delete(f"/clubs/{club.id}/members/2")

    assert response.status_code == 200


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
