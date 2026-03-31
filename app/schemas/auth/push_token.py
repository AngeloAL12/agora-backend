from pydantic import BaseModel, Field


class PushTokenRequest(BaseModel):
    push_token: str = Field(..., min_length=1)
