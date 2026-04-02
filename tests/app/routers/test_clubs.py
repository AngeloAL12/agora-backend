from fastapi.testclient import TestClient

from app.core.security import get_current_user
from app.main import app
from app.models.club.club import Club
from app.models.club.club_category import ClubCategory
from app.models.club.club_member import ClubMember
from app.schemas.auth.auth import CurrentUser


def override_user(user_id=1):
    return lambda: CurrentUser(id=user_id, role="user")


def create_category(db, name="Deportes"):
    category = ClubCategory(name=name)
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


def create_club(db, category_id, leader_id=1, name="Club Test", description="Desc"):
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

    db.add(ClubMember(id_club=club.id, id_user=2))
    db.add(ClubMember(id_club=club.id, id_user=3))
    db.commit()

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

    db.add(ClubMember(id_club=club.id, id_user=2))
    db.commit()

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
    response = client.post("/join", json={"club_id": club.id})

    assert response.status_code == 200
    assert response.json()["message"] == "Te uniste al club"


def test_join_club_not_found(db, clear_dependency_overrides):
    app.dependency_overrides[get_current_user] = override_user(2)

    client = TestClient(app)
    response = client.post("/join", json={"club_id": 999})

    assert response.status_code == 404
    assert response.json()["detail"] == "Club no encontrado"


def test_join_club_already_member(db, clear_dependency_overrides):
    app.dependency_overrides[get_current_user] = override_user(2)

    category = create_category(db)
    club = create_club(db, category.id)

    db.add(ClubMember(id_club=club.id, id_user=2))
    db.commit()

    client = TestClient(app)
    response = client.post("/join", json={"club_id": club.id})

    assert response.status_code == 400
    assert response.json()["detail"] == "Ya eres miembro"


def test_leave_club(db, clear_dependency_overrides):
    app.dependency_overrides[get_current_user] = override_user(2)

    category = create_category(db)
    club = create_club(db, category.id)

    client = TestClient(app)
    client.post("/join", json={"club_id": club.id})

    response = client.request(
        "DELETE",
        "/members/me",
        json={"club_id": club.id},
    )

    assert response.status_code == 200
    assert response.json()["message"] == "Saliste del club"


def test_leave_club_not_found(db, clear_dependency_overrides):
    app.dependency_overrides[get_current_user] = override_user(2)

    client = TestClient(app)
    response = client.request(
        "DELETE",
        "/members/me",
        json={"club_id": 999},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Club no encontrado"


def test_leave_club_not_member(db, clear_dependency_overrides):
    app.dependency_overrides[get_current_user] = override_user(2)

    category = create_category(db)
    club = create_club(db, category.id)

    client = TestClient(app)
    response = client.request(
        "DELETE",
        "/members/me",
        json={"club_id": club.id},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "No eres miembro"


def test_leave_club_leader_cannot_leave(db, clear_dependency_overrides):
    app.dependency_overrides[get_current_user] = override_user(1)

    category = create_category(db)
    club = create_club(db, category.id, leader_id=1)

    client = TestClient(app)
    response = client.request(
        "DELETE",
        "/members/me",
        json={"club_id": club.id},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "El líder no puede salirse"


def test_remove_member_only_leader(db, clear_dependency_overrides):
    app.dependency_overrides[get_current_user] = override_user(2)

    category = create_category(db)
    club = create_club(db, category.id, leader_id=1)

    db.add(ClubMember(id_club=club.id, id_user=3))
    db.commit()

    client = TestClient(app)
    response = client.request(
        "DELETE",
        "/members/3",
        json={"club_id": club.id},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Solo el líder puede expulsar"


def test_remove_member_club_not_found(db, clear_dependency_overrides):
    app.dependency_overrides[get_current_user] = override_user(1)

    client = TestClient(app)
    response = client.request(
        "DELETE",
        "/members/2",
        json={"club_id": 999},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Club no encontrado"


def test_remove_member_not_member(db, clear_dependency_overrides):
    app.dependency_overrides[get_current_user] = override_user(1)

    category = create_category(db)
    club = create_club(db, category.id, leader_id=1)

    client = TestClient(app)
    response = client.request(
        "DELETE",
        "/members/999",
        json={"club_id": club.id},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "No es miembro"


def test_remove_member_success(db, clear_dependency_overrides):
    app.dependency_overrides[get_current_user] = override_user(1)

    category = create_category(db)
    club = create_club(db, category.id, leader_id=1)

    db.add(ClubMember(id_club=club.id, id_user=2))
    db.commit()

    client = TestClient(app)
    response = client.request(
        "DELETE",
        "/members/2",
        json={"club_id": club.id},
    )

    assert response.status_code == 200
    assert response.json()["message"] == "Miembro expulsado"


def test_transfer_leadership(db, clear_dependency_overrides):
    app.dependency_overrides[get_current_user] = override_user(1)

    category = create_category(db)
    club = create_club(db, category.id, leader_id=1)

    client = TestClient(app)

    app.dependency_overrides[get_current_user] = override_user(2)
    client.post("/join", json={"club_id": club.id})

    app.dependency_overrides[get_current_user] = override_user(1)
    response = client.post(
        f"/clubs/{club.id}/transfer-leadership",
        json={"new_leader_id": 2},
    )

    assert response.status_code == 200
    assert response.json()["message"] == "Liderazgo transferido"


def test_transfer_leadership_club_not_found(db, clear_dependency_overrides):
    app.dependency_overrides[get_current_user] = override_user(1)

    client = TestClient(app)
    response = client.post(
        "/clubs/999/transfer-leadership",
        json={"new_leader_id": 2},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Club no encontrado"


def test_transfer_leadership_only_leader(db, clear_dependency_overrides):
    app.dependency_overrides[get_current_user] = override_user(2)

    category = create_category(db)
    club = create_club(db, category.id, leader_id=1)

    db.add(ClubMember(id_club=club.id, id_user=2))
    db.commit()

    client = TestClient(app)
    response = client.post(
        f"/clubs/{club.id}/transfer-leadership",
        json={"new_leader_id": 2},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Solo el líder puede transferir"


def test_transfer_leadership_requires_membership(db, clear_dependency_overrides):
    app.dependency_overrides[get_current_user] = override_user(1)

    category = create_category(db)
    club = create_club(db, category.id, leader_id=1)

    client = TestClient(app)
    response = client.post(
        f"/clubs/{club.id}/transfer-leadership",
        json={"new_leader_id": 2},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Debe ser miembro"
