import pytest
from fastapi.testclient import TestClient

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


def override_user(user_id=1):
    return lambda: CurrentUser(id=user_id, role=RoleName.USER)


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


def create_category(db, name="Deportes"):
    category = ClubCategory(name=name)
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


def create_club(
    db,
    category_id,
    leader_id=1,
    name="Club Test",
    description="Desc",
):
    ensure_user(db, leader_id)

    club = Club(
        name=name,
        description=description,
        id_category=category_id,
        id_leader=leader_id,
    )
    db.add(club)
    db.commit()
    db.refresh(club)
    return club


def create_membership(db, club_id, user_id):
    ensure_user(db, user_id)
    db.add(ClubMember(id_club=club_id, id_user=user_id))
    db.commit()


def test_get_clubs(db):
    category = create_category(db)

    create_club(
        db,
        category.id,
        name="Club Uno",
    )

    create_club(
        db,
        category.id,
        leader_id=2,
        name="Club Dos",
    )

    client = TestClient(app)
    response = client.get("/clubs")

    assert response.status_code == 200
    assert len(response.json()) == 2


def test_get_club_not_found():
    client = TestClient(app)

    response = client.get("/clubs/999")

    assert response.status_code == 404


def test_create_club_with_image(db, monkeypatch):
    app.dependency_overrides[get_current_user] = override_user(1)

    async def fake_upload(*args, **kwargs):
        return "clubs/images/test.png"

    monkeypatch.setattr(
        storage_service,
        "upload_file",
        fake_upload,
    )

    category = create_category(db)
    client = TestClient(app)

    response = client.post(
        "/clubs",
        data={
            "name": "Club Img",
            "description": "Desc",
            "id_category": str(category.id),
        },
        files={
            "image": ("file.png", b"img", "image/png"),
        },
    )

    assert response.status_code == 201
    assert response.json()["image"] == "clubs/images/test.png"


def test_update_club_with_image(db, monkeypatch):
    app.dependency_overrides[get_current_user] = override_user(1)

    async def fake_upload(*args, **kwargs):
        return "clubs/images/update.png"

    monkeypatch.setattr(
        storage_service,
        "upload_file",
        fake_upload,
    )

    category = create_category(db)
    club = create_club(db, category.id)

    client = TestClient(app)
    response = client.patch(
        f"/clubs/{club.id}",
        files={"image": ("file.png", b"img", "image/png")},
    )

    assert response.status_code == 200
    assert response.json()["image"] == "clubs/images/update.png"


def test_update_errors(db):
    app.dependency_overrides[get_current_user] = override_user(1)

    category = create_category(db)
    club = create_club(db, category.id)

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
        data={"id_category": "999"},
    )
    assert res.status_code == 400


def test_delete_club(db):
    app.dependency_overrides[get_current_user] = override_user(1)

    category = create_category(db)
    club = create_club(db, category.id)

    client = TestClient(app)
    response = client.delete(f"/clubs/{club.id}")

    assert response.status_code == 200


def test_join_leave_flow(db):
    category = create_category(db)
    club = create_club(db, category.id)

    app.dependency_overrides[get_current_user] = override_user(2)
    client = TestClient(app)

    assert client.post(f"/clubs/{club.id}/members").status_code == 200

    assert client.delete(f"/clubs/{club.id}/members/me").status_code == 200


def test_remove_member(db):
    category = create_category(db)
    club = create_club(db, category.id)

    create_membership(db, club.id, 2)

    app.dependency_overrides[get_current_user] = override_user(1)
    client = TestClient(app)

    response = client.delete(f"/clubs/{club.id}/members/2")

    assert response.status_code == 200


def test_transfer_leadership(db):
    category = create_category(db)
    club = create_club(db, category.id)

    create_membership(db, club.id, 2)

    app.dependency_overrides[get_current_user] = override_user(1)
    client = TestClient(app)

    response = client.patch(f"/clubs/{club.id}/members/2/leader")

    assert response.status_code == 200
