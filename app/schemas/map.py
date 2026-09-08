from datetime import datetime

from pydantic import BaseModel, ConfigDict


class BuildingMediaResponse(BaseModel):
    id: int
    url: str
    floor: int

    model_config = ConfigDict(from_attributes=True)


class PointMediaResponse(BaseModel):
    id: int
    url: str

    model_config = ConfigDict(from_attributes=True)


class BuildingDetailResponse(BaseModel):
    id: int
    name: str
    description: str | None
    images: list[BuildingMediaResponse]
    views_360: list[BuildingMediaResponse]
    created_at: datetime


class PointOfInterestDetailResponse(BaseModel):
    id: int
    name: str
    description: str | None
    latitude: float | None
    longitude: float | None
    images: list[PointMediaResponse]
    views_360: list[PointMediaResponse]
    created_at: datetime
