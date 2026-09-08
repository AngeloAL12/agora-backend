from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.complaint.complaint import Complaint


class ComplaintImage(Base):
    __tablename__ = "complaint_image"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    id_complaint: Mapped[int] = mapped_column(
        ForeignKey("complaint.id"), nullable=False
    )
    url: Mapped[str] = mapped_column(String(500), nullable=False)

    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    complaint: Mapped["Complaint"] = relationship("Complaint", back_populates="images")
