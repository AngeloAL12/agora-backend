from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from app.schemas.club.user import UserOut


class JoinRequestAction(StrEnum):
    ACCEPT = "accept"
    REJECT = "reject"


class JoinRequestActionBody(BaseModel):
    action: JoinRequestAction


class JoinRequestResponse(BaseModel):
    id: int
    id_club: int
    id_user: int
    status: str
    created_at: datetime
    user: UserOut

    model_config = ConfigDict(from_attributes=True)
