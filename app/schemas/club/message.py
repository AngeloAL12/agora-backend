from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ClubMessageUserResponse(BaseModel):
    id: int
    name: str
    photo: str | None

    model_config = ConfigDict(from_attributes=True)


class ClubMessageResponse(BaseModel):
    id: int
    id_club: int
    content: str
    created_at: datetime
    user: ClubMessageUserResponse

    model_config = ConfigDict(from_attributes=True)


class ClubMessageInput(BaseModel):
    content: str = Field(..., min_length=1, max_length=1000)
