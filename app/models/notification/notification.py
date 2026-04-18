from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy import Enum as SQLAlchemyEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.auth.user import User


class NotificationCategory(StrEnum):
    REPORTS = "REPORTS"
    # TODO: CLUBS = "CLUBS"


class NotificationEventType(StrEnum):
    COMPLAINT_SUBMITTED = "COMPLAINT_SUBMITTED"
    COMPLAINT_IN_PROGRESS = "COMPLAINT_IN_PROGRESS"
    COMPLAINT_RESOLVED = "COMPLAINT_RESOLVED"
    COMPLAINT_REJECTED = "COMPLAINT_REJECTED"


class Notification(Base):
    __tablename__ = "notification"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    id_user: Mapped[int] = mapped_column(
        ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True
    )
    category: Mapped[NotificationCategory] = mapped_column(
        SQLAlchemyEnum(NotificationCategory), nullable=False
    )
    event_type: Mapped[NotificationEventType] = mapped_column(
        SQLAlchemyEnum(NotificationEventType), nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    reference_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped["User"] = relationship("User", back_populates="notifications")
