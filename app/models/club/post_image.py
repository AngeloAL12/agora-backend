from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.club.post import ClubPost


class ClubPostImage(Base):
    __tablename__ = "club_post_image"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    id_post: Mapped[int] = mapped_column(ForeignKey("club_post.id"), nullable=False)

    # Relationships
    post: Mapped["ClubPost"] = relationship(
        "ClubPost",
        back_populates="images",
        lazy="joined",
    )
