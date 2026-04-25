from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models import User
    from app.models.club.post import ClubPost


class ClubPostComment(Base):
    __tablename__ = "club_post_comment"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    id_post: Mapped[int] = mapped_column(ForeignKey("club_post.id"), nullable=False)
    id_user: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped["User"] = relationship(
        "User",
        foreign_keys=[id_user],
        lazy="joined",
    )
    post: Mapped["ClubPost"] = relationship(
        "ClubPost",
        back_populates="comments",
    )
