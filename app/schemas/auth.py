from pydantic import BaseModel, EmailStr

from app.core.roles import RoleName


class TokenRequest(BaseModel):
    """
    Schema para recibir el token de Google o Microsoft
    desde el cliente móvil.
    """

    token: str


class LoginRequest(BaseModel):
    """
    Schema para las solicitudes de login/registro.
    """

    email: EmailStr
    name: str
    photo: str | None = None
    oauth_provider: str
    oauth_sub: str


class CurrentUser(BaseModel):
    """
    Representa al usuario autenticado que devuelve 'get_current_user'.
    Nota: Este objeto NO es el modelo de base de datos (User),
    por lo que solo tiene estos dos campos.
    """

    id: int
    role: RoleName
