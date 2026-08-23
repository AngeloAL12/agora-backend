from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy import Enum as SQLAlchemyEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.auth.user import User


class ContentTargetType(StrEnum):
    POST = "POST"
    COMMENT = "COMMENT"
    MESSAGE = "MESSAGE"


class ContentReportReason(StrEnum):
    HARASSMENT = "HARASSMENT"
    HATE_SPEECH = "HATE_SPEECH"
    SEXUAL_CONTENT = "SEXUAL_CONTENT"
    VIOLENCE = "VIOLENCE"
    SPAM = "SPAM"
    PERSONAL_INFORMATION = "PERSONAL_INFORMATION"
    OTHER = "OTHER"


class ContentReportStatus(StrEnum):
    PENDING = "PENDING"
    IN_REVIEW = "IN_REVIEW"
    RESOLVED = "RESOLVED"
    DISMISSED = "DISMISSED"


class ModerationAction(StrEnum):
    NONE = "NONE"
    REMOVE_CONTENT = "REMOVE_CONTENT"
    SUSPEND_USER = "SUSPEND_USER"
    REMOVE_AND_SUSPEND = "REMOVE_AND_SUSPEND"


class ContentReport(Base):
    __tablename__ = "content_report"
    __table_args__ = (
        UniqueConstraint(
            "reporter_id",
            "target_type",
            "target_id",
            name="uq_content_report_reporter_target",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    reporter_id: Mapped[int] = mapped_column(
        ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True
    )
    reported_user_id: Mapped[int] = mapped_column(
        ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True
    )
    moderator_id: Mapped[int | None] = mapped_column(
        ForeignKey("user.id", ondelete="SET NULL"), nullable=True
    )
    target_type: Mapped[ContentTargetType] = mapped_column(
        SQLAlchemyEnum(ContentTargetType), nullable=False, index=True
    )
    target_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    club_id: Mapped[int] = mapped_column(
        ForeignKey("club.id", ondelete="CASCADE"), nullable=False, index=True
    )
    reason: Mapped[ContentReportReason] = mapped_column(
        SQLAlchemyEnum(ContentReportReason), nullable=False
    )
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_snapshot: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[ContentReportStatus] = mapped_column(
        SQLAlchemyEnum(ContentReportStatus),
        default=ContentReportStatus.PENDING,
        nullable=False,
        index=True,
    )
    action_taken: Mapped[ModerationAction] = mapped_column(
        SQLAlchemyEnum(ModerationAction),
        default=ModerationAction.NONE,
        nullable=False,
    )
    moderator_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    reporter: Mapped["User"] = relationship(
        "User", foreign_keys=[reporter_id], lazy="joined"
    )
    reported_user: Mapped["User"] = relationship(
        "User", foreign_keys=[reported_user_id], lazy="joined"
    )
    moderator: Mapped["User | None"] = relationship(
        "User", foreign_keys=[moderator_id], lazy="joined"
    )
