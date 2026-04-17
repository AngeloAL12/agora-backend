from fastapi.testclient import TestClient

from app.core.roles import RoleName
from app.core.security import get_current_user
from app.main import app
from app.models.notification.notification import (
    Notification,
    NotificationCategory,
    NotificationEventType,
)
from app.schemas.auth.auth import CurrentUser
from tests.app.routers.test_complaints import _create_user


def _override_current_user(user_id: int):
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        id=user_id,
        role=RoleName.USER,
    )


def _create_notification(db, user_id: int, **kwargs) -> Notification:
    defaults = {
        "id_user": user_id,
        "category": NotificationCategory.REPORTS,
        "event_type": NotificationEventType.COMPLAINT_SUBMITTED,
        "title": "Test",
        "body": "Test body",
        "is_read": False,
        "reference_id": None,
    }
    defaults.update(kwargs)
    n = Notification(**defaults)
    db.add(n)
    db.commit()
    db.refresh(n)
    return n


def test_get_notifications_empty_returns_empty_list(db, clear_dependency_overrides):
    user = _create_user(db, RoleName.USER, "notif1@itmexicali.edu.mx", "notif-sub-1")
    _override_current_user(user.id)

    client = TestClient(app)
    response = client.get("/notifications")

    assert response.status_code == 200
    data = response.json()
    assert data["items"] == []
    assert data["total"] == 0


def test_get_notifications_returns_newest_first(db, clear_dependency_overrides):
    user = _create_user(db, RoleName.USER, "notif2@itmexicali.edu.mx", "notif-sub-2")
    _override_current_user(user.id)

    n1 = _create_notification(db, user.id, title="First")
    n2 = _create_notification(db, user.id, title="Second")

    client = TestClient(app)
    response = client.get("/notifications")

    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 2
    assert items[0]["id"] == n2.id
    assert items[1]["id"] == n1.id


def test_get_notifications_filtered_by_category(db, clear_dependency_overrides):
    user = _create_user(db, RoleName.USER, "notif3@itmexicali.edu.mx", "notif-sub-3")
    _override_current_user(user.id)

    _create_notification(db, user.id, category=NotificationCategory.REPORTS)

    client = TestClient(app)
    response = client.get("/notifications?category=REPORTS")
    assert response.status_code == 200
    assert response.json()["total"] == 1

    response_no_match = client.get("/notifications?category=invalid")
    assert response_no_match.status_code == 422


def test_get_notifications_pagination(db, clear_dependency_overrides):
    user = _create_user(db, RoleName.USER, "notif4@itmexicali.edu.mx", "notif-sub-4")
    _override_current_user(user.id)

    for i in range(5):
        _create_notification(db, user.id, title=f"Notif {i}")

    client = TestClient(app)
    response = client.get("/notifications?limit=2&offset=0")
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 2
    assert data["total"] == 5
    assert data["limit"] == 2
    assert data["offset"] == 0

    response2 = client.get("/notifications?limit=2&offset=2")
    assert len(response2.json()["items"]) == 2


def test_get_notifications_only_own(db, clear_dependency_overrides):
    user1 = _create_user(db, RoleName.USER, "notif5a@itmexicali.edu.mx", "notif-sub-5a")
    user2 = _create_user(db, RoleName.USER, "notif5b@itmexicali.edu.mx", "notif-sub-5b")

    _create_notification(db, user1.id)
    _create_notification(db, user2.id)

    _override_current_user(user1.id)
    client = TestClient(app)
    response = client.get("/notifications")

    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["id"]


def test_mark_notification_read_success(db, clear_dependency_overrides):
    user = _create_user(db, RoleName.USER, "notif6@itmexicali.edu.mx", "notif-sub-6")
    _override_current_user(user.id)
    n = _create_notification(db, user.id)

    client = TestClient(app)
    response = client.patch(f"/notifications/{n.id}/read")

    assert response.status_code == 200
    assert response.json()["is_read"] is True

    db.refresh(n)
    assert n.is_read is True


def test_mark_notification_read_wrong_user_returns_404(db, clear_dependency_overrides):
    user1 = _create_user(db, RoleName.USER, "notif7a@itmexicali.edu.mx", "notif-sub-7a")
    user2 = _create_user(db, RoleName.USER, "notif7b@itmexicali.edu.mx", "notif-sub-7b")
    n = _create_notification(db, user1.id)

    _override_current_user(user2.id)
    client = TestClient(app)
    response = client.patch(f"/notifications/{n.id}/read")

    assert response.status_code == 404


def test_mark_notification_read_nonexistent_returns_404(db, clear_dependency_overrides):
    user = _create_user(db, RoleName.USER, "notif8@itmexicali.edu.mx", "notif-sub-8")
    _override_current_user(user.id)

    client = TestClient(app)
    response = client.patch("/notifications/99999/read")

    assert response.status_code == 404


def test_mark_all_read_only_affects_current_user(db, clear_dependency_overrides):
    user1 = _create_user(db, RoleName.USER, "notif9a@itmexicali.edu.mx", "notif-sub-9a")
    user2 = _create_user(db, RoleName.USER, "notif9b@itmexicali.edu.mx", "notif-sub-9b")
    n1 = _create_notification(db, user1.id)
    n2 = _create_notification(db, user2.id)

    _override_current_user(user1.id)
    client = TestClient(app)
    response = client.post("/notifications/read-all")

    assert response.status_code == 204

    db.refresh(n1)
    db.refresh(n2)
    assert n1.is_read is True
    assert n2.is_read is False


def test_mark_all_read_is_idempotent(db, clear_dependency_overrides):
    user = _create_user(db, RoleName.USER, "notif10@itmexicali.edu.mx", "notif-sub-10")
    _override_current_user(user.id)
    _create_notification(db, user.id, is_read=True)

    client = TestClient(app)
    response = client.post("/notifications/read-all")
    assert response.status_code == 204


def test_create_complaint_schedules_submitted_notification(
    db, clear_dependency_overrides, monkeypatch
):
    calls = []

    def fake_notify(user_id, complaint_id, complaint_title):
        calls.append(
            {"user_id": user_id, "complaint_id": complaint_id, "title": complaint_title}
        )

    monkeypatch.setattr(
        "app.routers.complaints._notify_complaint_submitted", fake_notify
    )

    async def fake_upload_file(file, bucket_name, prefix):
        return f"{prefix}/stored.png"

    async def fake_get_presigned_url(bucket_name, object_key, expiration=3600):
        return f"https://cdn.example.com/{object_key}"

    monkeypatch.setattr(
        "app.routers.complaints.storage_service.upload_file", fake_upload_file
    )
    monkeypatch.setattr(
        "app.routers.complaints.storage_service.get_presigned_url",
        fake_get_presigned_url,
    )

    user = _create_user(db, RoleName.USER, "notif11@itmexicali.edu.mx", "notif-sub-11")
    _override_current_user(user.id)

    client = TestClient(app)
    response = client.post(
        "/complaints",
        data={
            "title": "Test Notif",
            "description": "Detalle",
            "category": "MAINTENANCE",
        },
    )

    assert response.status_code == 201
    assert len(calls) == 1
    assert calls[0]["user_id"] == user.id
    assert calls[0]["title"] == "Test Notif"


def test_status_update_schedules_notification(
    db, clear_dependency_overrides, monkeypatch
):
    from app.core.security import get_current_user as gcu
    from app.models.complaint.complaint import Complaint, ComplaintStatus

    calls = []

    def fake_notify(user_id, complaint_id, complaint_title, new_status):
        calls.append({"user_id": user_id, "new_status": new_status})

    monkeypatch.setattr(
        "app.routers.complaints._notify_complaint_status_changed", fake_notify
    )

    staff_user = _create_user(
        db, RoleName.STAFF, "staff1@itmexicali.edu.mx", "staff-sub-1"
    )
    owner = _create_user(db, RoleName.USER, "notif12@itmexicali.edu.mx", "notif-sub-12")

    complaint = Complaint(
        id_user=owner.id,
        type="REPORT",
        title="Mi queja",
        description="Detalle",
        category="MAINTENANCE",
        status=ComplaintStatus.PENDING,
    )
    db.add(complaint)
    db.commit()
    db.refresh(complaint)

    app.dependency_overrides[gcu] = lambda: CurrentUser(
        id=staff_user.id, role=RoleName.STAFF
    )

    client = TestClient(app)
    response = client.patch(
        f"/complaints/{complaint.id}/status",
        json={"status": "IN_PROGRESS"},
    )
    assert response.status_code == 200

    assert len(calls) == 1
    assert calls[0]["user_id"] == owner.id
    assert calls[0]["new_status"] == ComplaintStatus.IN_PROGRESS


def test_status_update_to_pending_does_not_schedule_notification(
    db, clear_dependency_overrides, monkeypatch
):
    from app.core.security import get_current_user as gcu
    from app.models.complaint.complaint import Complaint, ComplaintStatus

    calls = []

    def fake_notify(user_id, complaint_id, complaint_title, new_status):
        calls.append(new_status)

    monkeypatch.setattr(
        "app.routers.complaints._notify_complaint_status_changed", fake_notify
    )

    staff_user = _create_user(
        db, RoleName.STAFF, "staff2@itmexicali.edu.mx", "staff-sub-2"
    )
    owner = _create_user(db, RoleName.USER, "notif13@itmexicali.edu.mx", "notif-sub-13")

    complaint = Complaint(
        id_user=owner.id,
        type="REPORT",
        title="Queja pendiente",
        description="Detalle",
        category="SECURITY",
        status=ComplaintStatus.IN_PROGRESS,
    )
    db.add(complaint)
    db.commit()
    db.refresh(complaint)

    app.dependency_overrides[gcu] = lambda: CurrentUser(
        id=staff_user.id, role=RoleName.STAFF
    )

    client = TestClient(app)
    client.patch(f"/complaints/{complaint.id}/status", json={"status": "PENDING"})

    assert len(calls) == 1
    assert calls[0] == ComplaintStatus.PENDING
