from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AuthorOut(BaseModel):
    id: int
    name: str

    model_config = ConfigDict(from_attributes=True)


class EventBase(BaseModel):
    title: str = Field(..., min_length=3, max_length=150)
    description: str = Field(..., max_length=500)
    date: datetime
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)

    @field_validator("date")
    @classmethod
    def date_must_be_future(cls, v: datetime):
        if v <= datetime.now(timezone.utc):
            raise ValueError("La fecha debe ser futura")
        return v


class EventCreate(EventBase):
    pass


class EventUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=150)
    description: str | None = Field(default=None, max_length=500)
    date: datetime | None = None
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)

    @field_validator("date")
    @classmethod
    def date_must_be_future(cls, v: datetime | None):
        if v and v <= datetime.now(timezone.utc):
            raise ValueError("La fecha debe ser futura")
        return v


class EventResponse(EventBase):
    id: int
    id_club: int
    created_at: datetime
    author: AuthorOut

    model_config = ConfigDict(from_attributes=True)