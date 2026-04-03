from fastapi.testclient import TestClient

from app.core.roles import RoleName
from app.core.security import get_current_user
from app.main import app
from app.models.auth.role import Role
from app.models.auth.user import User
from app.models.complaint.complaint import Complaint, ComplaintCategory, ComplaintStatus
from app.schemas.auth.auth import CurrentUser


def _override_current_user(user_id: int = 1):
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        id=user_id,
        role=RoleName.USER,
    )


def _create_user(db, role_name: str, email: str, oauth_sub: str) -> User:
    role = db.query(Role).filter(Role.name == role_name).one_or_none()
    if role is None:
        role = Role(name=role_name)
        db.add(role)
        db.flush()

    user = User(
        email=email,
        oauth_provider="google",
        oauth_sub=oauth_sub,
        name=email.split("@")[0],
        id_role=role.id,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def test_create_complaint_with_image(db, clear_dependency_overrides, monkeypatch):
    user = _create_user(db, RoleName.USER, "student1@itmexicali.edu.mx", "sub-1")
    _override_current_user(user.id)

    async def fake_upload_file(file, bucket_name, prefix):
        assert bucket_name
        assert prefix == "complaints/1/images"
        return f"{prefix}/stored-image.png"

    async def fake_get_presigned_url(bucket_name, object_key, expiration=3600):
        assert bucket_name
        assert object_key == "complaints/1/images/stored-image.png"
        return f"https://cdn.example.com/{object_key}"

    monkeypatch.setattr(
        "app.routers.complaints.storage_service.upload_file",
        fake_upload_file,
    )
    monkeypatch.setattr(
        "app.routers.complaints.storage_service.get_presigned_url",
        fake_get_presigned_url,
    )

    client = TestClient(app)
    response = client.post(
        "/complaints/with-images",
        data={
            "title": "Beca",
            "description": "No se reflejo el pago",
            "category": "ACADEMIC",
        },
        files=[("images", ("evidence.png", b"image-bytes", "image/png"))],
    )

    assert response.status_code == 201
    assert response.json()["title"] == "Beca"
    assert response.json()["category"] == "ACADEMIC"
    assert response.json()["status"] == ComplaintStatus.PENDING
    assert response.json()["images"] == [
        {
            "id": 1,
            "url": "https://cdn.example.com/complaints/1/images/stored-image.png",
            "created_at": response.json()["images"][0]["created_at"],
        }
    ]

    complaint = db.query(Complaint).filter(Complaint.id == 1).one()
    assert complaint.id_user == user.id
    assert complaint.status == ComplaintStatus.PENDING
    assert len(complaint.images) == 1
    assert len(complaint.status_history) == 1


def test_get_my_complaints_returns_only_owned_items(db, clear_dependency_overrides):
    user = _create_user(db, RoleName.USER, "student2@itmexicali.edu.mx", "sub-2")
    other_user = _create_user(db, RoleName.USER, "student3@itmexicali.edu.mx", "sub-3")
    _override_current_user(user.id)

    db.add(
        Complaint(
            id_user=user.id,
            title="Mi queja",
            description="Detalle",
            category=ComplaintCategory.ACADEMIC,
            status=ComplaintStatus.PENDING,
        )
    )
    db.add(
        Complaint(
            id_user=other_user.id,
            title="Ajena",
            description="No debe salir",
            category=ComplaintCategory.SECURITY,
            status=ComplaintStatus.IN_PROGRESS,
        )
    )
    db.commit()

    client = TestClient(app)
    response = client.get("/complaints/me")

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["title"] == "Mi queja"


def test_get_my_complaint_detail_returns_owned_complaint(
    db, clear_dependency_overrides, monkeypatch
):
    user = _create_user(db, RoleName.USER, "student4@itmexicali.edu.mx", "sub-4")
    _override_current_user(user.id)

    complaint = Complaint(
        id_user=user.id,
        title="Detalle",
        description="Texto largo",
        category=ComplaintCategory.ACADEMIC,
        status=ComplaintStatus.PENDING,
    )
    db.add(complaint)
    db.commit()

    async def fake_get_presigned_url(bucket_name, object_key, expiration=3600):
        return f"https://cdn.example.com/{object_key}"

    monkeypatch.setattr(
        "app.routers.complaints.storage_service.get_presigned_url",
        fake_get_presigned_url,
    )

    client = TestClient(app)
    response = client.get(f"/complaints/{complaint.id}")

    assert response.status_code == 200
    assert response.json()["id"] == complaint.id
    assert response.json()["title"] == "Detalle"
    assert response.json()["images"] == []


def test_get_my_complaint_detail_forbidden_for_other_user(
    db, clear_dependency_overrides, monkeypatch
):
    user = _create_user(db, RoleName.USER, "student5@itmexicali.edu.mx", "sub-5")
    other_user = _create_user(db, RoleName.USER, "student6@itmexicali.edu.mx", "sub-6")
    _override_current_user(user.id)

    complaint = Complaint(
        id_user=other_user.id,
        title="Privada",
        description="No visible",
        category=ComplaintCategory.SECURITY,
        status=ComplaintStatus.PENDING,
    )
    db.add(complaint)
    db.commit()

    async def fake_get_presigned_url(bucket_name, object_key, expiration=3600):
        return f"https://cdn.example.com/{object_key}"

    monkeypatch.setattr(
        "app.routers.complaints.storage_service.get_presigned_url",
        fake_get_presigned_url,
    )

    client = TestClient(app)
    response = client.get(f"/complaints/{complaint.id}")

    assert response.status_code == 403
    assert response.json()["detail"] == "No tienes acceso a esta queja"


def test_create_complaint_json_endpoint(db, clear_dependency_overrides):
    """Test creating complaint via JSON endpoint"""
    user = _create_user(db, RoleName.USER, "student11@itmexicali.edu.mx", "sub-11")
    _override_current_user(user.id)

    client = TestClient(app)
    response = client.post(
        "/complaints",
        json={
            "title": "JSON Complaint",
            "description": "Created via JSON endpoint",
            "category": "SECURITY"
        }
    )

    assert response.status_code == 201
    assert response.json()["title"] == "JSON Complaint"
    assert response.json()["category"] == "SECURITY"
    assert response.json()["status"] == ComplaintStatus.PENDING
    assert len(response.json()["images"]) == 0


def test_create_complaint_with_too_many_images(
    db, clear_dependency_overrides, monkeypatch
):
    """Test that more than 3 images is rejected"""
    user = _create_user(db, RoleName.USER, "student12@itmexicali.edu.mx", "sub-12")
    _override_current_user(user.id)

    client = TestClient(app)
    response = client.post(
        "/complaints/with-images",
        data={
            "title": "Too Many Images",
            "description": "This complaint has 4 images",
            "category": "ACADEMIC"
        },
        files=[
            ("images", ("img1.png", b"image1", "image/png")),
            ("images", ("img2.png", b"image2", "image/png")),
            ("images", ("img3.png", b"image3", "image/png")),
            ("images", ("img4.png", b"image4", "image/png")),
        ]
    )

    assert response.status_code == 400
    assert "3" in response.json()["detail"]


def test_get_complaint_not_found(db, clear_dependency_overrides):
    """Test that requesting nonexistent complaint returns 404"""
    user = _create_user(db, RoleName.USER, "student13@itmexicali.edu.mx", "sub-13")
    _override_current_user(user.id)

    client = TestClient(app)
    response = client.get("/complaints/9999")

    assert response.status_code == 404
    assert "no encontrada" in response.json()["detail"].lower()
