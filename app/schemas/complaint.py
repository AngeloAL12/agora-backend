from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.complaint.complaint import ComplaintCategory, ComplaintStatus


class ComplaintCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: str = Field(..., min_length=1)
    category: ComplaintCategory


class ComplaintImageResponse(BaseModel):
    id: int
    url: str
    created_at: datetime | Any = Field(..., description="Creation timestamp")

    model_config = ConfigDict(from_attributes=True)


class ComplaintResponse(BaseModel):
    id: int
    title: str
    description: str
    category: ComplaintCategory
    status: ComplaintStatus
    has_appealed: bool
    created_at: datetime | Any = Field(..., description="Creation timestamp")
    images: list[ComplaintImageResponse]

    model_config = ConfigDict(from_attributes=True)


class ComplaintListItemResponse(BaseModel):
    id: int
    title: str
    status: ComplaintStatus
    created_at: datetime | Any = Field(..., description="Creation timestamp")
