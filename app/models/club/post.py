from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models import User
    from app.models.club.post_comment import ClubPostComment
    from app.models.club.post_image import ClubPostImage
    from app.models.club.post_like import ClubPostLike


class ClubPost(Base):
    __tablename__ = "club_post"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    id_club: Mapped[int] = mapped_column(
        ForeignKey("club.id", ondelete="CASCADE"), nullable=False
    )
    id_author: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    author: Mapped["User"] = relationship(
        "User",
        foreign_keys=[id_author],
        lazy="joined",
    )
    images: Mapped[list["ClubPostImage"]] = relationship(
        "ClubPostImage",
        back_populates="post",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="joined",
    )
    likes: Mapped[list["ClubPostLike"]] = relationship(
        "ClubPostLike",
        back_populates="post",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="selectin",
    )
    comments: Mapped[list["ClubPostComment"]] = relationship(
        "ClubPostComment",
        back_populates="post",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="ClubPostComment.created_at.asc()",
        lazy="selectin",
    )
