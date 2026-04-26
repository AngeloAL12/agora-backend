from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.club.user import UserOut


class EventBase(BaseModel):
    title: str = Field(..., min_length=3, max_length=150)
    description: str | None = Field(default=None, max_length=500)
    date: datetime
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)


class EventCreate(EventBase):
    @field_validator("date")
    @classmethod
    def date_must_be_future(cls, v: datetime):
        if v.tzinfo is None:
            v = v.replace(tzinfo=UTC)
        if v <= datetime.now(UTC):
            raise ValueError("La fecha debe ser futura")
        return v


class EventUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=150)
    description: str | None = Field(default=None, max_length=500)
    date: datetime | None = None
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)

    @field_validator("date")
    @classmethod
    def date_must_be_future(cls, v: datetime | None):
        if v is not None:
            if v.tzinfo is None:
                v = v.replace(tzinfo=UTC)
            if v <= datetime.now(UTC):
                raise ValueError("La fecha debe ser futura")
        return v


class EventResponse(BaseModel):
    id: int
    id_club: int
    title: str
    description: str | None
    date: datetime
    latitude: float | None
    longitude: float | None
    created_at: datetime
    author: UserOut

    model_config = ConfigDict(from_attributes=True)
