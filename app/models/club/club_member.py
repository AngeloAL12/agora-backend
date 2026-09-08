from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.auth.user import User
    from app.models.club.club import Club


class ClubMember(Base):
    __tablename__ = "club_member"
    __table_args__ = (UniqueConstraint("id_club", "id_user"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    id_club: Mapped[int] = mapped_column(
        ForeignKey("club.id", ondelete="CASCADE"), nullable=False
    )
    id_user: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False)
    joined_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    club: Mapped["Club"] = relationship(back_populates="members")
    user: Mapped["User"] = relationship(back_populates="club_memberships")
