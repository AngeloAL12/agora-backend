from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.notification.notification import Notification, NotificationCategory
from app.schemas.auth.auth import CurrentUser
from app.schemas.notification import (
    NotificationListResponse,
    NotificationReadResponse,
)

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=NotificationListResponse)
def get_notifications(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    category: NotificationCategory | None = Query(default=None),
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    base_filter = Notification.id_user == current_user.id
    count_query = select(func.count()).select_from(Notification).where(base_filter)
    items_query = select(Notification).where(base_filter)

    if category is not None:
        count_query = count_query.where(Notification.category == category)
        items_query = items_query.where(Notification.category == category)

    total = db.execute(count_query).scalar_one()
    items = (
        db.execute(
            items_query.order_by(Notification.created_at.desc(), Notification.id.desc())
            .limit(limit)
            .offset(offset)
        )
        .scalars()
        .all()
    )

    return NotificationListResponse(
        items=items, total=total, limit=limit, offset=offset
    )


@router.patch("/{notification_id}/read", response_model=NotificationReadResponse)
def mark_notification_read(
    notification_id: int,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    notification = db.execute(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.id_user == current_user.id,
        )
    ).scalar_one_or_none()

    if notification is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notificación no encontrada",
        )

    notification.is_read = True
    db.commit()
    db.refresh(notification)
    return notification


@router.post("/read-all", status_code=status.HTTP_204_NO_CONTENT)
def mark_all_notifications_read(
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    db.execute(
        update(Notification)
        .where(
            Notification.id_user == current_user.id,
            Notification.is_read == False,  # noqa: E712
        )
        .values(is_read=True)
    )
    db.commit()
