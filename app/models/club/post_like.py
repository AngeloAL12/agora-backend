from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models import User
    from app.models.club.post import ClubPost


class ClubPostLike(Base):
    __tablename__ = "club_post_like"
    __table_args__ = (
        UniqueConstraint("id_post", "id_user", name="uq_club_post_like_post_user"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    id_post: Mapped[int] = mapped_column(ForeignKey("club_post.id"), nullable=False)
    id_user: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False)

    # Relationships
    user: Mapped["User"] = relationship(
        "User",
        foreign_keys=[id_user],
        lazy="joined",
    )
    post: Mapped["ClubPost"] = relationship(
        "ClubPost",
        back_populates="likes",
        lazy="joined",
    )
