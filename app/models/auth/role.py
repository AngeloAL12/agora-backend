from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.auth.staff_whitelist import StaffWhitelist
    from app.models.auth.user import User


class Role(Base):
    __tablename__ = "role"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    users: Mapped[list["User"]] = relationship(back_populates="role")
    staff_whitelist_entries: Mapped[list["StaffWhitelist"]] = relationship(
        back_populates="role"
    )
