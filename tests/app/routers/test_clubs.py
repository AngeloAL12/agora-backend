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


@pytest.fixture(autouse=True)
def seed_club_users(db):
    ensure_user(db, 1)
    ensure_user(db, 2)
    ensure_user(db, 3)


def override_user(user_id=1):
    return lambda: CurrentUser(id=user_id, role=RoleName.USER)


def ensure_user(db, user_id: int):
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


def create_membership(db, club_id: int, user_id: int):
    ensure_user(db, user_id)
    db.add(ClubMember(id_club=club_id, id_user=user_id))
    db.commit()


def create_category(db, name="Deportes"):
    category = ClubCategory(name=name)
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


def create_club(db, category_id, leader_id=1, name="Club Test", description="Desc"):
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


def test_get_clubs_empty(db, clear_dependency_overrides):
    client = TestClient(app)

    response = client.get("/clubs")

    assert response.status_code == 200
    assert response.json() == []


def test_create_club(db, clear_dependency_overrides):
    app.dependency_overrides[get_current_user] = override_user()

    category = create_category(db)
    client = TestClient(app)

    response = client.post(
        "/clubs",
        json={
            "name": "Club A",
            "description": "Desc",
            "id_category": category.id,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Club A"
    assert data["id_leader"] == 1
    assert data["id_category"] == category.id


def test_create_club_duplicate_name(db, clear_dependency_overrides):
    app.dependency_overrides[get_current_user] = override_user(1)

    category = create_category(db)
    create_club(db, category.id, leader_id=1)

    client = TestClient(app)
    response = client.post(
        "/clubs",
        json={
            "name": "Club Test",
            "description": "Otro",
            "id_category": category.id,
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Nombre de club ya existe"


def test_create_club_invalid_category(db, clear_dependency_overrides):
    app.dependency_overrides[get_current_user] = override_user(1)

    client = TestClient(app)
    response = client.post(
        "/clubs",
        json={
            "name": "Club Sin Categoria Valida",
            "description": "Desc",
            "id_category": 999,
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Categoría inválida"


def test_get_club_detail(db, clear_dependency_overrides):
    category = create_category(db)
    club = create_club(db, category.id)

    client = TestClient(app)
    response = client.get(f"/clubs/{club.id}")

    assert response.status_code == 200
    assert response.json()["id"] == club.id


def test_get_club_detail_members_count(db, clear_dependency_overrides):
    category = create_category(db)
    club = create_club(db, category.id)

    create_membership(db, club.id, 2)
    create_membership(db, club.id, 3)

    client = TestClient(app)
    response = client.get(f"/clubs/{club.id}")

    assert response.status_code == 200
    assert response.json()["members_count"] == 2


def test_get_club_not_found(clear_dependency_overrides):
    client = TestClient(app)

    response = client.get("/clubs/999")

    assert response.status_code == 404
    assert response.json()["detail"] == "Club no encontrado"


def test_update_club_only_leader(db, clear_dependency_overrides):
    app.dependency_overrides[get_current_user] = override_user(2)

    category = create_category(db)
    club = create_club(db, category.id, leader_id=1)

    client = TestClient(app)
    response = client.patch(
        f"/clubs/{club.id}",
        json={"name": "Nuevo Nombre"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Solo el líder puede editar"


def test_update_club_not_found(db, clear_dependency_overrides):
    app.dependency_overrides[get_current_user] = override_user(1)

    client = TestClient(app)
    response = client.patch(
        "/clubs/999",
        json={"name": "Nuevo Nombre"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Club no encontrado"


def test_update_club_success(db, clear_dependency_overrides):
    app.dependency_overrides[get_current_user] = override_user(1)

    category1 = create_category(db, "Deportes")
    category2 = create_category(db, "Tecnologia")
    club = create_club(db, category1.id, leader_id=1)

    client = TestClient(app)
    response = client.patch(
        f"/clubs/{club.id}",
        json={
            "name": "Club Actualizado",
            "description": "Nueva descripcion",
            "image": "https://example.com/club.png",
            "id_category": category2.id,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Club Actualizado"
    assert data["description"] == "Nueva descripcion"
    assert data["image"] == "https://example.com/club.png"
    assert data["id_category"] == category2.id


def test_update_club_can_clear_image_with_null(db, clear_dependency_overrides):
    app.dependency_overrides[get_current_user] = override_user(1)

    category = create_category(db)
    club = create_club(db, category.id, leader_id=1, name="Club Imagen")
    club.image = "https://example.com/club.png"
    db.commit()
    db.refresh(club)

    client = TestClient(app)
    response = client.patch(
        f"/clubs/{club.id}",
        json={"image": None},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["image"] is None

    db.refresh(club)
    assert club.image is None


def test_update_club_duplicate_name(db, clear_dependency_overrides):
    app.dependency_overrides[get_current_user] = override_user(1)

    category = create_category(db)
    club1 = create_club(db, category.id, leader_id=1, name="Club Uno")
    create_club(db, category.id, leader_id=2, name="Club Dos")

    client = TestClient(app)
    response = client.patch(
        f"/clubs/{club1.id}",
        json={"name": "Club Dos"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Nombre de club ya existe"


def test_update_club_invalid_category(db, clear_dependency_overrides):
    app.dependency_overrides[get_current_user] = override_user(1)

    category = create_category(db)
    club = create_club(db, category.id, leader_id=1)

    client = TestClient(app)
    response = client.patch(
        f"/clubs/{club.id}",
        json={"id_category": 999},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Categoría inválida"


def test_update_club_rejects_null_name(db, clear_dependency_overrides):
    app.dependency_overrides[get_current_user] = override_user(1)

    category = create_category(db)
    club = create_club(db, category.id, leader_id=1)

    client = TestClient(app)
    response = client.patch(
        f"/clubs/{club.id}",
        json={"name": None},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "El nombre no puede ser null"


def test_update_club_rejects_null_description(db, clear_dependency_overrides):
    app.dependency_overrides[get_current_user] = override_user(1)

    category = create_category(db)
    club = create_club(db, category.id, leader_id=1)

    client = TestClient(app)
    response = client.patch(
        f"/clubs/{club.id}",
        json={"description": None},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "La descripción no puede ser null"


def test_delete_club_only_leader(db, clear_dependency_overrides):
    app.dependency_overrides[get_current_user] = override_user(2)

    category = create_category(db)
    club = create_club(db, category.id, leader_id=1)

    client = TestClient(app)
    response = client.delete(f"/clubs/{club.id}")

    assert response.status_code == 403
    assert response.json()["detail"] == "Solo el líder puede eliminar"


def test_delete_club_not_found(db, clear_dependency_overrides):
    app.dependency_overrides[get_current_user] = override_user(1)

    client = TestClient(app)
    response = client.delete("/clubs/999")

    assert response.status_code == 404
    assert response.json()["detail"] == "Club no encontrado"


def test_delete_club_success(db, clear_dependency_overrides):
    app.dependency_overrides[get_current_user] = override_user(1)

    category = create_category(db)
    club = create_club(db, category.id, leader_id=1)

    create_membership(db, club.id, 2)

    client = TestClient(app)
    response = client.delete(f"/clubs/{club.id}")

    assert response.status_code == 200
    assert response.json()["message"] == "Club eliminado"
    assert db.query(Club).filter(Club.id == club.id).first() is None
    assert db.query(ClubMember).filter(ClubMember.id_club == club.id).count() == 0


def test_join_club(db, clear_dependency_overrides):
    app.dependency_overrides[get_current_user] = override_user(2)

    category = create_category(db)
    club = create_club(db, category.id)

    client = TestClient(app)
    response = client.post(f"/clubs/{club.id}/members")

    assert response.status_code == 200
    assert response.json()["message"] == "Te uniste al club"


def test_join_club_not_found(db, clear_dependency_overrides):
    app.dependency_overrides[get_current_user] = override_user(2)

    client = TestClient(app)
    response = client.post("/clubs/999/members")

    assert response.status_code == 404
    assert response.json()["detail"] == "Club no encontrado"


def test_join_club_already_member(db, clear_dependency_overrides):
    app.dependency_overrides[get_current_user] = override_user(2)

    category = create_category(db)
    club = create_club(db, category.id)

    create_membership(db, club.id, 2)

    client = TestClient(app)
    response = client.post(f"/clubs/{club.id}/members")

    assert response.status_code == 400
    assert response.json()["detail"] == "Ya eres miembro"


def test_leave_club(db, clear_dependency_overrides):
    app.dependency_overrides[get_current_user] = override_user(2)

    category = create_category(db)
    club = create_club(db, category.id)

    client = TestClient(app)
    client.post(f"/clubs/{club.id}/members")

    response = client.delete(f"/clubs/{club.id}/members/me")

    assert response.status_code == 200
    assert response.json()["message"] == "Saliste del club"


def test_leave_club_not_found(db, clear_dependency_overrides):
    app.dependency_overrides[get_current_user] = override_user(2)

    client = TestClient(app)
    response = client.delete("/clubs/999/members/me")

    assert response.status_code == 404
    assert response.json()["detail"] == "Club no encontrado"


def test_leave_club_not_member(db, clear_dependency_overrides):
    app.dependency_overrides[get_current_user] = override_user(2)

    category = create_category(db)
    club = create_club(db, category.id)

    client = TestClient(app)
    response = client.delete(f"/clubs/{club.id}/members/me")

    assert response.status_code == 404
    assert response.json()["detail"] == "No eres miembro"


def test_leave_club_leader_cannot_leave(db, clear_dependency_overrides):
    app.dependency_overrides[get_current_user] = override_user(1)

    category = create_category(db)
    club = create_club(db, category.id, leader_id=1)

    client = TestClient(app)
    response = client.delete(f"/clubs/{club.id}/members/me")

    assert response.status_code == 400
    assert response.json()["detail"] == "El líder no puede salirse"


def test_remove_member_only_leader(db, clear_dependency_overrides):
    app.dependency_overrides[get_current_user] = override_user(2)

    category = create_category(db)
    club = create_club(db, category.id, leader_id=1)

    create_membership(db, club.id, 3)

    client = TestClient(app)
    response = client.delete(f"/clubs/{club.id}/members/3")

    assert response.status_code == 403
    assert response.json()["detail"] == "Solo el líder puede expulsar"


def test_remove_member_club_not_found(db, clear_dependency_overrides):
    app.dependency_overrides[get_current_user] = override_user(1)

    client = TestClient(app)
    response = client.delete("/clubs/999/members/2")

    assert response.status_code == 404
    assert response.json()["detail"] == "Club no encontrado"


def test_remove_member_not_member(db, clear_dependency_overrides):
    app.dependency_overrides[get_current_user] = override_user(1)

    category = create_category(db)
    club = create_club(db, category.id, leader_id=1)

    client = TestClient(app)
    response = client.delete(f"/clubs/{club.id}/members/999")

    assert response.status_code == 404
    assert response.json()["detail"] == "No es miembro"


def test_remove_member_success(db, clear_dependency_overrides):
    app.dependency_overrides[get_current_user] = override_user(1)

    category = create_category(db)
    club = create_club(db, category.id, leader_id=1)

    create_membership(db, club.id, 2)

    client = TestClient(app)
    response = client.delete(f"/clubs/{club.id}/members/2")

    assert response.status_code == 200
    assert response.json()["message"] == "Miembro expulsado"


def test_transfer_leadership(db, clear_dependency_overrides):
    app.dependency_overrides[get_current_user] = override_user(1)

    category = create_category(db)
    club = create_club(db, category.id, leader_id=1)

    client = TestClient(app)

    app.dependency_overrides[get_current_user] = override_user(2)
    client.post(f"/clubs/{club.id}/members")

    app.dependency_overrides[get_current_user] = override_user(1)
    response = client.patch(f"/clubs/{club.id}/members/2/leader")

    assert response.status_code == 200
    assert response.json()["message"] == "Liderazgo transferido"

    db.refresh(club)
    assert club.id_leader == 2


def test_transfer_leadership_club_not_found(db, clear_dependency_overrides):
    app.dependency_overrides[get_current_user] = override_user(1)

    client = TestClient(app)
    response = client.patch("/clubs/999/members/2/leader")

    assert response.status_code == 404
    assert response.json()["detail"] == "Club no encontrado"


def test_transfer_leadership_only_leader(db, clear_dependency_overrides):
    app.dependency_overrides[get_current_user] = override_user(2)

    category = create_category(db)
    club = create_club(db, category.id, leader_id=1)

    create_membership(db, club.id, 2)

    client = TestClient(app)
    response = client.patch(f"/clubs/{club.id}/members/2/leader")

    assert response.status_code == 403
    assert response.json()["detail"] == "Solo el líder actual puede transferir"


def test_transfer_leadership_requires_membership(db, clear_dependency_overrides):
    app.dependency_overrides[get_current_user] = override_user(1)

    category = create_category(db)
    club = create_club(db, category.id, leader_id=1)

    client = TestClient(app)
    response = client.patch(f"/clubs/{club.id}/members/2/leader")

    assert response.status_code == 400
    assert response.json()["detail"] == "El usuario destino debe ser miembro del club"


def test_transfer_leadership_same_leader_rejected(db, clear_dependency_overrides):
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


def test_delete_event_not_found(db, clear_dependency_overrides):
    app.dependency_overrides[get_current_user] = override_user(1)

    category = create_category(db)
    club = create_club(db, category.id, leader_id=1)

    client = TestClient(app)
    response = client.delete(f"/clubs/{club.id}/events/999")

    assert response.status_code == 404
    assert response.json()["detail"] == "Evento no encontrado"


# --- Tests de Publicaciones ---


def test_get_club_posts_empty(db, clear_dependency_overrides):
    app.dependency_overrides[get_current_user] = override_user(1)

    category = create_category(db)
    club = create_club(db, category.id, leader_id=1)
    create_membership(db, club.id, 1)

    client = TestClient(app)
    response = client.get(f"/clubs/{club.id}/posts")

    assert response.status_code == 200
    assert response.json() == []


def test_create_club_post(db, clear_dependency_overrides):
    app.dependency_overrides[get_current_user] = override_user(1)

    category = create_category(db)
    club = create_club(db, category.id, leader_id=1)

    client = TestClient(app)
    response = client.post(
        f"/clubs/{club.id}/posts",
        json={
            "content": "Nueva publicación",
            "images": ["https://example.com/img1.jpg"],
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["content"] == "Nueva publicación"
    assert data["id_club"] == club.id
    assert data["like_count"] == 0
    assert data["user_has_liked"] is False
    assert data["comment_count"] == 0
    assert len(data["images"]) == 1
    assert data["author"]["id"] == 1
