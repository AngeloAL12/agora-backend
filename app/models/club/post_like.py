from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.club.post import ClubPost


class ClubPostLike(Base):
    __tablename__ = "club_post_like"

    id_post: Mapped[int] = mapped_column(
        ForeignKey("club_post.id"),
        primary_key=True,
        nullable=False,
    )
    id_user: Mapped[int] = mapped_column(
        ForeignKey("user.id"),
        primary_key=True,
        nullable=False,
    )

    post: Mapped["ClubPost"] = relationship(
        "ClubPost",
        back_populates="likes",
    )
