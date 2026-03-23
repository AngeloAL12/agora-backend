from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class StaffWhitelist(Base):
    __tablename__ = "staff_whitelist"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    id_role: Mapped[int] = mapped_column(
        Integer, ForeignKey("roles.id"), nullable=False
    )
