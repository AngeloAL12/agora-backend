from pydantic import BaseModel, EmailStr

from app.core.roles import RoleName


class LoginRequest(BaseModel):
    email: EmailStr
    name: str
    photo: str | None = None
    oauth_provider: str
    oauth_sub: str


class CurrentUser(BaseModel):
    id: int
    role: RoleName
