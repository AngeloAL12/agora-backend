from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ClubCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str = Field(..., min_length=1, max_length=250)
    id_category: int
    image: str | None = Field(default=None, max_length=500)


class ClubUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, min_length=1, max_length=250)
    id_category: int | None = None
    image: str | None = Field(default=None, max_length=500)


class TransferLeadershipRequest(BaseModel):
    new_leader_id: int


class ClubResponse(BaseModel):
    id: int
    name: str
    description: str
    image: str | None
    id_category: int
    id_leader: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ClubDetailResponse(ClubResponse):
    members_count: int
