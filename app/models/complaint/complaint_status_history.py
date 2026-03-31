from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, func
from sqlalchemy import Enum as SQLAlchemyEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.complaint.complaint import ComplaintStatus

if TYPE_CHECKING:
    from app.models.auth.user import User
    from app.models.complaint.complaint import Complaint


class ComplaintStatusHistory(Base):
    __tablename__ = "complaint_status_history"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    id_complaint: Mapped[int] = mapped_column(
        ForeignKey("complaint.id"), nullable=False
    )
    id_user: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False)

    old_status: Mapped[ComplaintStatus | None] = mapped_column(
        SQLAlchemyEnum(ComplaintStatus), nullable=True
    )
    new_status: Mapped[ComplaintStatus] = mapped_column(
        SQLAlchemyEnum(ComplaintStatus), nullable=False
    )

    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    complaint: Mapped["Complaint"] = relationship(
        "Complaint", back_populates="status_history"
    )
    user: Mapped["User"] = relationship(
        "User", back_populates="complaint_status_histories"
    )
