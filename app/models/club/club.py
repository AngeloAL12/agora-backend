from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.auth.user import User
    from app.models.club.club_category import ClubCategory
    from app.models.club.club_member import ClubMember
    from app.models.club.message import ClubMessage


class Club(Base):
    __tablename__ = "club"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(String(250), nullable=False)

    profile_image: Mapped[str | None] = mapped_column(String(500), nullable=True)
    cover_image: Mapped[str | None] = mapped_column(String(500), nullable=True)

    id_category: Mapped[int] = mapped_column(
        ForeignKey("club_category.id"), nullable=False
    )
    id_leader: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False)
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    category: Mapped["ClubCategory"] = relationship(back_populates="clubs")
    leader: Mapped["User"] = relationship(back_populates="clubs_led")
    members: Mapped[list["ClubMember"]] = relationship(
        back_populates="club", passive_deletes=True
    )
    messages: Mapped[list["ClubMessage"]] = relationship(back_populates="club")
