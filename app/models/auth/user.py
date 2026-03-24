from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.auth.role import Role
    from app.models.auth.user_session import UserSession


class User(Base):
    __tablename__ = "user"
    __table_args__ = (
        UniqueConstraint(
            "oauth_provider",
            "oauth_sub",
            name="uq_user_oauth_provider_oauth_sub",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    oauth_provider: Mapped[str] = mapped_column(String(50), nullable=False)
    oauth_sub: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    photo: Mapped[str | None] = mapped_column(String(500), nullable=True)
    id_role: Mapped[int] = mapped_column(ForeignKey("role.id"), nullable=False)
    id_career: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    role: Mapped["Role"] = relationship(back_populates="users")
    sessions: Mapped[list["UserSession"]] = relationship(back_populates="user")
