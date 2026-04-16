from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ClubCategoryResponse(BaseModel):
    id: int
    name: str

    model_config = ConfigDict(from_attributes=True)


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
