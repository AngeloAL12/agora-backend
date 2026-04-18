from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.complaint.complaint import (
    ComplaintCategory,
    ComplaintStatus,
    ComplaintType,
)


class ComplaintCreateRequest(BaseModel):
    type: ComplaintType = Field(default=ComplaintType.REPORT)
    title: str = Field(..., min_length=1, max_length=255)
    description: str = Field(..., min_length=1)
    category: ComplaintCategory
    id_building: int | None = None
    classroom: str | None = Field(default=None, max_length=255)


class ComplaintImageResponse(BaseModel):
    id: int
    url: str
    created_at: datetime | Any = Field(..., description="Creation timestamp")

    model_config = ConfigDict(from_attributes=True)


class ComplaintResponse(BaseModel):
    id: int
    type: ComplaintType
    title: str
    description: str
    category: ComplaintCategory
    id_building: int | None = None
    classroom: str | None = None
    status: ComplaintStatus
    has_appealed: bool
    created_at: datetime | Any = Field(..., description="Creation timestamp")
    images: list[ComplaintImageResponse]

    model_config = ConfigDict(from_attributes=True)


class ComplaintListItemResponse(BaseModel):
    id: int
    type: ComplaintType
    title: str
    status: ComplaintStatus
    created_at: datetime | Any = Field(..., description="Creation timestamp")

    model_config = ConfigDict(from_attributes=True)


# Alias para el listado de admin (misma forma)
ComplaintOut = ComplaintListItemResponse


class ComplaintStatusUpdate(BaseModel):
    status: ComplaintStatus


class ComplaintUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, min_length=1)
