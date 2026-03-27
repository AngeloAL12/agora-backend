from pydantic import BaseModel


class PushTokenRequest(BaseModel):
    push_token: str