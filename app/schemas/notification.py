from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.notification.notification import (
    NotificationCategory,
    NotificationEventType,
)


class NotificationResponse(BaseModel):
    id: int
    category: NotificationCategory
    event_type: NotificationEventType
    title: str
    body: str
    is_read: bool
    reference_id: int | None
    created_at: datetime | Any = Field(..., description="ISO 8601 timestamp")

    model_config = ConfigDict(from_attributes=True)


class NotificationListResponse(BaseModel):
    items: list[NotificationResponse]
    total: int
    limit: int
    offset: int


class NotificationReadResponse(BaseModel):
    id: int
    is_read: bool

    model_config = ConfigDict(from_attributes=True)
