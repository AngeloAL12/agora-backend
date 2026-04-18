from app.core.roles import RoleName
from app.models.auth.user_session import UserSession
from app.models.notification.notification import (
    Notification,
    NotificationCategory,
    NotificationEventType,
)
from app.services.notification_service import create_notification
from tests.app.routers.test_complaints import _create_user


def test_create_notification_sends_push_when_user_has_token(db, monkeypatch):
    user = _create_user(db, RoleName.USER, "push1@itmexicali.edu.mx", "push-sub-1")
    db.add(
        UserSession(
            id=1,
            id_user=user.id,
            token_version=1,
            push_token="ExponentPushToken[token-1]",
        )
    )
    db.commit()

    sent = []

    def fake_send_push_notification(token, title, body, data=None):
        sent.append({"token": token, "title": title, "body": body, "data": data or {}})

    monkeypatch.setattr(
        "app.services.notification_service.send_push_notification",
        fake_send_push_notification,
    )

    notification = create_notification(
        db,
        id_user=user.id,
        category=NotificationCategory.REPORTS,
        event_type=NotificationEventType.COMPLAINT_SUBMITTED,
        title="Queja enviada",
        body="Tu queja fue recibida.",
        reference_id=123,
    )

    assert notification.id is not None
    assert len(sent) == 1
    assert sent[0]["token"] == "ExponentPushToken[token-1]"
    assert sent[0]["title"] == "Queja enviada"
    assert sent[0]["body"] == "Tu queja fue recibida."
    assert sent[0]["data"]["reference_id"] == 123
    assert sent[0]["data"]["notification_id"] == notification.id


def test_create_notification_does_not_send_push_without_session(db, monkeypatch):
    user = _create_user(db, RoleName.USER, "push2@itmexicali.edu.mx", "push-sub-2")

    sent = []

    monkeypatch.setattr(
        "app.services.notification_service.send_push_notification",
        lambda *args, **kwargs: sent.append("called"),
    )

    create_notification(
        db,
        id_user=user.id,
        category=NotificationCategory.REPORTS,
        event_type=NotificationEventType.COMPLAINT_SUBMITTED,
        title="Titulo",
        body="Cuerpo",
    )

    assert sent == []


def test_create_notification_does_not_send_push_without_token(db, monkeypatch):
    user = _create_user(db, RoleName.USER, "push3@itmexicali.edu.mx", "push-sub-3")
    db.add(UserSession(id=2, id_user=user.id, token_version=1, push_token=None))
    db.commit()

    sent = []

    monkeypatch.setattr(
        "app.services.notification_service.send_push_notification",
        lambda *args, **kwargs: sent.append("called"),
    )

    create_notification(
        db,
        id_user=user.id,
        category=NotificationCategory.REPORTS,
        event_type=NotificationEventType.COMPLAINT_SUBMITTED,
        title="Titulo",
        body="Cuerpo",
    )

    assert sent == []


def test_create_notification_still_persists_when_push_sender_raises(db, monkeypatch):
    user = _create_user(db, RoleName.USER, "push4@itmexicali.edu.mx", "push-sub-4")
    db.add(
        UserSession(
            id=3,
            id_user=user.id,
            token_version=1,
            push_token="ExponentPushToken[token-4]",
        )
    )
    db.commit()

    def fail_push(*args, **kwargs):
        raise RuntimeError("expo unavailable")

    monkeypatch.setattr(
        "app.services.notification_service.send_push_notification",
        fail_push,
    )

    notification = create_notification(
        db,
        id_user=user.id,
        category=NotificationCategory.REPORTS,
        event_type=NotificationEventType.COMPLAINT_SUBMITTED,
        title="Titulo",
        body="Cuerpo",
    )

    persisted = (
        db.query(Notification).filter(Notification.id == notification.id).one_or_none()
    )
    assert persisted is not None
