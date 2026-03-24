from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.auth.role import Role


class StaffWhitelist(Base):
    __tablename__ = "staff_whitelist"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    id_role: Mapped[int] = mapped_column(ForeignKey("role.id"), nullable=False)

    role: Mapped["Role"] = relationship(back_populates="staff_whitelist_entries")
