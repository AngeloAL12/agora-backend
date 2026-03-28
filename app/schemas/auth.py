from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    email: EmailStr
    name: str
    photo: str | None = None
    oauth_provider: str
    oauth_sub: str


class CurrentUser(BaseModel):
    id: int
    role: str
