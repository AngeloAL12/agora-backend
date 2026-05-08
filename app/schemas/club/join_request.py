from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from app.models.club.club_join_request import JoinRequestStatus
from app.schemas.club.user import UserOut


class JoinRequestAction(StrEnum):
    ACCEPT = "ACCEPT"
    REJECT = "REJECT"


class JoinRequestActionBody(BaseModel):
    action: JoinRequestAction


class JoinRequestResponse(BaseModel):
    id: int
    id_club: int
    id_user: int
    status: JoinRequestStatus
    created_at: datetime
    user: UserOut

    model_config = ConfigDict(from_attributes=True)
