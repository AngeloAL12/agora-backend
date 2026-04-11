from datetime import datetime

from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Building(Base):
    __tablename__ = "building"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    images: Mapped[list["BuildingImage"]] = relationship(
        back_populates="building", cascade="all, delete-orphan"
    )
    images_360: Mapped[list["Building360"]] = relationship(
        back_populates="building", cascade="all, delete-orphan"
    )


class BuildingImage(Base):
    __tablename__ = "building_image"

    id: Mapped[int] = mapped_column(primary_key=True)
    id_building: Mapped[int] = mapped_column(
        ForeignKey("building.id", ondelete="CASCADE"), nullable=False
    )
    url: Mapped[str] = mapped_column(String(255), nullable=False)
    floor: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    building: Mapped["Building"] = relationship(back_populates="images")


class Building360(Base):
    __tablename__ = "building_360"

    id: Mapped[int] = mapped_column(primary_key=True)
    id_building: Mapped[int] = mapped_column(
        ForeignKey("building.id", ondelete="CASCADE"), nullable=False
    )
    url: Mapped[str] = mapped_column(String(255), nullable=False)
    floor: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    building: Mapped["Building"] = relationship(back_populates="images_360")


class PointOfInterest(Base):
    __tablename__ = "point_of_interest"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    images: Mapped[list["PointOfInterestImage"]] = relationship(
        back_populates="point_of_interest", cascade="all, delete-orphan"
    )
    images_360: Mapped[list["PointOfInterest360"]] = relationship(
        back_populates="point_of_interest", cascade="all, delete-orphan"
    )


class PointOfInterestImage(Base):
    __tablename__ = "point_of_interest_image"

    id: Mapped[int] = mapped_column(primary_key=True)
    id_point: Mapped[int] = mapped_column(
        ForeignKey("point_of_interest.id", ondelete="CASCADE"), nullable=False
    )
    url: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    point_of_interest: Mapped["PointOfInterest"] = relationship(back_populates="images")


class PointOfInterest360(Base):
    __tablename__ = "point_of_interest_360"

    id: Mapped[int] = mapped_column(primary_key=True)
    id_point: Mapped[int] = mapped_column(
        ForeignKey("point_of_interest.id", ondelete="CASCADE"), nullable=False
    )
    url: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    point_of_interest: Mapped["PointOfInterest"] = relationship(
        back_populates="images_360"
    )
