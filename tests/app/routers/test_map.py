from fastapi.testclient import TestClient

from app.core.roles import RoleName
from app.core.security import get_current_user
from app.main import app
from app.models.campus import (
    Building,
    Building360,
    BuildingImage,
    PointOfInterest,
    PointOfInterest360,
    PointOfInterestImage,
)
from app.schemas.auth.auth import CurrentUser


def _override_current_user(user_id: int = 1):
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        id=user_id,
        role=RoleName.USER,
    )


def test_get_building_detail_success(db, clear_dependency_overrides, monkeypatch):
    _override_current_user()

    building = Building(
        name="Edificio A",
        description="Aulas de ingeniería en sistemas.",
    )
    db.add(building)
    db.flush()

    db.add_all(
        [
            BuildingImage(
                id_building=building.id,
                url="buildings/a1.jpg",
                floor=1,
            ),
            BuildingImage(
                id_building=building.id,
                url="buildings/a2.jpg",
                floor=2,
            ),
            Building360(
                id_building=building.id,
                url="360/a_piso1.jpg",
                floor=1,
            ),
            Building360(
                id_building=building.id,
                url="360/a_piso2.jpg",
                floor=2,
            ),
        ]
    )
    db.commit()

    async def fake_get_presigned_url(bucket_name, object_key, expiration=3600):
        assert bucket_name
        return f"https://storage.app/{object_key}"

    monkeypatch.setattr(
        "app.routers.map.storage_service.get_presigned_url",
        fake_get_presigned_url,
    )

    client = TestClient(app)
    response = client.get(f"/map/buildings/{building.id}")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == building.id
    assert data["name"] == "Edificio A"
    assert data["description"] == "Aulas de ingeniería en sistemas."
    assert len(data["images"]) == 2
    assert len(data["views_360"]) == 2
    assert data["images"][0]["floor"] == 1
    assert data["images"][1]["floor"] == 2
    assert data["views_360"][0]["floor"] == 1
    assert data["views_360"][1]["floor"] == 2


def test_get_building_detail_not_found(db, clear_dependency_overrides):
    _override_current_user()

    client = TestClient(app)
    response = client.get("/map/buildings/9999")

    assert response.status_code == 404
    assert response.json()["detail"] == "Edificio no encontrado"


def test_get_point_of_interest_detail_success(
    db,
    clear_dependency_overrides,
    monkeypatch,
):
    _override_current_user()

    point = PointOfInterest(
        name="Cafetería Central",
        description="Cafetería principal del campus, abierta de 7am a 7pm.",
        latitude=32.6278,
        longitude=-115.4545,
    )
    db.add(point)
    db.flush()

    db.add_all(
        [
            PointOfInterestImage(
                id_point=point.id,
                url="points/cafeteria1.jpg",
            ),
            PointOfInterest360(
                id_point=point.id,
                url="360/cafeteria.jpg",
            ),
        ]
    )
    db.commit()

    async def fake_get_presigned_url(bucket_name, object_key, expiration=3600):
        assert bucket_name
        return f"https://storage.app/{object_key}"

    monkeypatch.setattr(
        "app.routers.map.storage_service.get_presigned_url",
        fake_get_presigned_url,
    )

    client = TestClient(app)
    response = client.get(f"/map/points/{point.id}")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == point.id
    assert data["name"] == "Cafetería Central"
    assert data["latitude"] == 32.6278
    assert data["longitude"] == -115.4545
    assert len(data["images"]) == 1
    assert len(data["views_360"]) == 1


def test_get_point_of_interest_detail_not_found(db, clear_dependency_overrides):
    _override_current_user()

    client = TestClient(app)
    response = client.get("/map/points/9999")

    assert response.status_code == 404
    assert response.json()["detail"] == "Punto de interés no encontrado"


def test_get_building_detail_invalid_token_returns_401(clear_dependency_overrides):
    client = TestClient(app)
    response = client.get(
        "/map/buildings/1",
        headers={"Authorization": "Bearer invalid-token"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Token inválido"


def test_get_point_detail_invalid_token_returns_401(clear_dependency_overrides):
    client = TestClient(app)
    response = client.get(
        "/map/points/1",
        headers={"Authorization": "Bearer invalid-token"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Token inválido"
