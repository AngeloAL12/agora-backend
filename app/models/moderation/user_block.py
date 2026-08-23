from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.auth.user import User


class UserBlock(Base):
    __tablename__ = "user_block"
    __table_args__ = (
        UniqueConstraint("blocker_id", "blocked_id", name="uq_user_block_pair"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    blocker_id: Mapped[int] = mapped_column(
        ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True
    )
    blocked_id: Mapped[int] = mapped_column(
        ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    blocker: Mapped["User"] = relationship(
        "User", foreign_keys=[blocker_id], lazy="joined"
    )
    blocked: Mapped["User"] = relationship(
        "User", foreign_keys=[blocked_id], lazy="joined"
    )
