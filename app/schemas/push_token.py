from pydantic import BaseModel


class PushTokenRequest(BaseModel):
    user_id: int
    push_token: str
