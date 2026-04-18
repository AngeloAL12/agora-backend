import logging

from sqlalchemy.orm import Session

from app.models.auth.user_session import UserSession
from app.models.notification.notification import (
    Notification,
    NotificationCategory,
    NotificationEventType,
)
from app.services.push_service import send_push_notification

logger = logging.getLogger(__name__)


def create_notification(
    db: Session,
    *,
    id_user: int,
    category: NotificationCategory,
    event_type: NotificationEventType,
    title: str,
    body: str,
    reference_id: int | None = None,
) -> Notification:
    notification = Notification(
        id_user=id_user,
        category=category,
        event_type=event_type,
        title=title,
        body=body,
        reference_id=reference_id,
    )
    db.add(notification)
    db.commit()

    session = db.query(UserSession).filter(UserSession.id_user == id_user).first()
    if session and session.push_token:
        try:
            send_push_notification(
                token=session.push_token,
                title=title,
                body=body,
                data={
                    "notification_id": notification.id,
                    "event_type": event_type,
                    "category": category,
                    "reference_id": reference_id,
                },
            )
        except Exception:
            logger.exception("Failed to trigger push notification send")

    return notification
