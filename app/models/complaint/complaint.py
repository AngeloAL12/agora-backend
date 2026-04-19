from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, func
from sqlalchemy import Enum as SQLAlchemyEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.auth.user import User
    from app.models.campus import Building
    from app.models.complaint.complaint_evidence import ComplaintEvidence
    from app.models.complaint.complaint_image import ComplaintImage
    from app.models.complaint.complaint_status_history import ComplaintStatusHistory


class ComplaintStatus(StrEnum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    RESOLVED = "RESOLVED"
    REJECTED = "REJECTED"


class ComplaintType(StrEnum):
    REPORT = "REPORT"
    SUGGESTION = "SUGGESTION"


class ComplaintCategory(StrEnum):
    MAINTENANCE = "MAINTENANCE"
    CLEANING = "CLEANING"
    SECURITY = "SECURITY"
    SERVICES = "SERVICES"
    INFRASTRUCTURE = "INFRASTRUCTURE"
    ACADEMIC = "ACADEMIC"
    OTHER = "OTHER"
    GENERAL = "GENERAL"


class Complaint(Base):
    __tablename__ = "complaint"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    id_user: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False)
    type: Mapped[ComplaintType] = mapped_column(
        SQLAlchemyEnum(ComplaintType), default=ComplaintType.REPORT, nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[ComplaintCategory] = mapped_column(
        SQLAlchemyEnum(ComplaintCategory), nullable=False
    )
    id_building: Mapped[int | None] = mapped_column(
        ForeignKey("building.id", ondelete="SET NULL"), nullable=True
    )
    classroom: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[ComplaintStatus] = mapped_column(
        SQLAlchemyEnum(ComplaintStatus), default=ComplaintStatus.PENDING, nullable=False
    )
    has_appealed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="complaints")
    building: Mapped["Building | None"] = relationship("Building")
    images: Mapped[list["ComplaintImage"]] = relationship(
        "ComplaintImage", back_populates="complaint", cascade="all, delete-orphan"
    )
    evidences: Mapped[list["ComplaintEvidence"]] = relationship(
        "ComplaintEvidence", back_populates="complaint", cascade="all, delete-orphan"
    )
    status_history: Mapped[list["ComplaintStatusHistory"]] = relationship(
        "ComplaintStatusHistory",
        back_populates="complaint",
        cascade="all, delete-orphan",
    )
