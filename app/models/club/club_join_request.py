import enum
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, UniqueConstraint
from sqlalchemy import Enum as SQLAlchemyEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.auth.user import User
    from app.models.club.club import Club


class JoinRequestStatus(enum.Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class ClubJoinRequest(Base):
    __tablename__ = "club_join_request"
    __table_args__ = (UniqueConstraint("id_club", "id_user"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    id_club: Mapped[int] = mapped_column(
        ForeignKey("club.id", ondelete="CASCADE"), nullable=False, index=True
    )
    id_user: Mapped[int] = mapped_column(
        ForeignKey("user.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[JoinRequestStatus] = mapped_column(
        SQLAlchemyEnum(JoinRequestStatus),
        default=JoinRequestStatus.PENDING,
        nullable=False,
    )
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    club: Mapped["Club"] = relationship(back_populates="join_requests")
    user: Mapped["User"] = relationship(back_populates="club_join_requests")
