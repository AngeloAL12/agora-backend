from fastapi.testclient import TestClient

from app.core.roles import RoleName
from app.core.security import get_current_user
from app.main import app
from app.models.auth.role import Role
from app.models.auth.user import User
from app.models.complaint.complaint import Complaint, ComplaintCategory, ComplaintStatus
from app.models.complaint.complaint_evidence import ComplaintEvidence
from app.schemas.auth.auth import CurrentUser


def _override_current_user(user_id: int = 1):
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        id=user_id,
        role=RoleName.USER,
    )


def _override_current_user_with_role(role: RoleName, user_id: int = 1):
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        id=user_id,
        role=role,
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
        "/complaints",
        data={
            "title": "Beca",
            "description": "No se reflejo el pago",
            "category": "MAINTENANCE",
        },
        files=[("images", ("evidence.png", b"image-bytes", "image/png"))],
    )

    assert response.status_code == 201
    assert response.json()["title"] == "Beca"
    assert response.json()["category"] == "MAINTENANCE"
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
            category=ComplaintCategory.MAINTENANCE,
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
        category=ComplaintCategory.MAINTENANCE,
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


def test_create_complaint_no_images(db, clear_dependency_overrides):
    """Test creating complaint without images via multipart endpoint"""
    user = _create_user(db, RoleName.USER, "student11@itmexicali.edu.mx", "sub-11")
    _override_current_user(user.id)

    client = TestClient(app)
    response = client.post(
        "/complaints",
        data={
            "title": "Sin Imágenes",
            "description": "Creada sin imágenes",
            "category": "SECURITY",
        },
    )

    assert response.status_code == 201
    assert response.json()["title"] == "Sin Imágenes"
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
        "/complaints",
        data={
            "title": "Too Many Images",
            "description": "This complaint has 4 images",
            "category": "MAINTENANCE",
        },
        files=[
            ("images", ("img1.png", b"image1", "image/png")),
            ("images", ("img2.png", b"image2", "image/png")),
            ("images", ("img3.png", b"image3", "image/png")),
            ("images", ("img4.png", b"image4", "image/png")),
        ],
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


def test_staff_can_access_get_all_complaints(db, clear_dependency_overrides):
    complaint_owner = _create_user(
        db,
        RoleName.USER,
        "student_staff@itmexicali.edu.mx",
        "sub-staff",
    )
    _override_current_user_with_role(RoleName.STAFF)

    db.add(
        Complaint(
            id_user=complaint_owner.id,
            title="Queja staff",
            description="Detalle",
            category=ComplaintCategory.MAINTENANCE,
            status=ComplaintStatus.PENDING,
        )
    )
    db.commit()

    client = TestClient(app)
    response = client.get("/complaints")

    assert response.status_code == 200


def test_non_staff_cannot_access_get_all_complaints(db, clear_dependency_overrides):
    user = _create_user(
        db,
        RoleName.USER,
        "student_no_staff@itmexicali.edu.mx",
        "sub-no-staff",
    )
    _override_current_user(user.id)

    client = TestClient(app)
    response = client.get("/complaints")

    assert response.status_code == 403
    assert "Staff" in response.json()["detail"]


def test_upload_evidence_complaint_not_found(db, clear_dependency_overrides):
    staff = _create_user(db, RoleName.STAFF, "staff404@itmexicali.edu.mx", "staff-404")
    _override_current_user_with_role(RoleName.STAFF, staff.id)

    client = TestClient(app)
    response = client.post(
        "/complaints/9999/evidence",
        files=[("file", ("evidence.png", b"evidence", "image/png"))],
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Queja no encontrada"


def test_upload_evidence_success(db, clear_dependency_overrides, monkeypatch):
    staff = _create_user(db, RoleName.STAFF, "staff_ok@itmexicali.edu.mx", "staff-ok")
    owner = _create_user(db, RoleName.USER, "owner@itmexicali.edu.mx", "owner-1")
    _override_current_user_with_role(RoleName.STAFF, staff.id)

    complaint = Complaint(
        id_user=owner.id,
        title="Queja con evidencia",
        description="Detalle",
        category=ComplaintCategory.ACADEMIC,
        status=ComplaintStatus.PENDING,
    )
    db.add(complaint)
    db.commit()
    db.refresh(complaint)

    async def fake_upload_file(file, bucket_name, prefix):
        assert bucket_name
        assert prefix == f"complaints/{complaint.id}/evidence"
        return f"{prefix}/stored-evidence.png"

    monkeypatch.setattr(
        "app.routers.complaints.storage_service.upload_file",
        fake_upload_file,
    )

    client = TestClient(app)
    response = client.post(
        f"/complaints/{complaint.id}/evidence",
        files=[("file", ("evidence.png", b"evidence", "image/png"))],
    )

    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "Evidencia subida y guardada exitosamente"
    assert (
        data["object_key"] == f"complaints/{complaint.id}/evidence/stored-evidence.png"
    )


def test_update_complaint_status_not_found(db, clear_dependency_overrides):
    staff = _create_user(
        db,
        RoleName.STAFF,
        "staff_status_nf@itmexicali.edu.mx",
        "staff-status-nf",
    )
    _override_current_user_with_role(RoleName.STAFF, staff.id)

    client = TestClient(app)
    response = client.patch("/complaints/9999/status", json={"status": "IN_PROGRESS"})

    assert response.status_code == 404
    assert response.json()["detail"] == "Queja no encontrada"


def test_update_complaint_status_resolved_without_evidence_returns_400(
    db, clear_dependency_overrides
):
    staff = _create_user(
        db,
        RoleName.STAFF,
        "staff_status400@itmexicali.edu.mx",
        "staff-status-400",
    )
    owner = _create_user(
        db,
        RoleName.USER,
        "owner_status400@itmexicali.edu.mx",
        "owner-status-400",
    )
    _override_current_user_with_role(RoleName.STAFF, staff.id)

    complaint = Complaint(
        id_user=owner.id,
        title="Sin evidencia",
        description="No debe resolver",
        category=ComplaintCategory.SECURITY,
        status=ComplaintStatus.PENDING,
    )
    db.add(complaint)
    db.commit()
    db.refresh(complaint)

    client = TestClient(app)
    response = client.patch(
        f"/complaints/{complaint.id}/status",
        json={"status": "RESOLVED"},
    )

    assert response.status_code == 400
    assert "sin antes subir una evidencia" in response.json()["detail"]


def test_update_complaint_status_success(db, clear_dependency_overrides):
    staff = _create_user(
        db,
        RoleName.STAFF,
        "staff_status_ok@itmexicali.edu.mx",
        "staff-status-ok",
    )
    owner = _create_user(
        db,
        RoleName.USER,
        "owner_status_ok@itmexicali.edu.mx",
        "owner-status-ok",
    )
    _override_current_user_with_role(RoleName.STAFF, staff.id)

    complaint = Complaint(
        id_user=owner.id,
        title="Actualizar estado",
        description="Detalle",
        category=ComplaintCategory.ACADEMIC,
        status=ComplaintStatus.PENDING,
    )
    db.add(complaint)
    db.flush()
    db.add(
        ComplaintEvidence(
            id_complaint=complaint.id,
            id_user=staff.id,
            url=f"complaints/{complaint.id}/evidence/manual.png",
        )
    )
    db.commit()

    client = TestClient(app)
    response = client.patch(
        f"/complaints/{complaint.id}/status",
        json={"status": "RESOLVED"},
    )

    assert response.status_code == 200
    assert response.json()["message"] == "Estado actualizado exitosamente"
    assert response.json()["new_status"] == "RESOLVED"
