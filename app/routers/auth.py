import requests as http_requests
from fastapi import APIRouter, Depends, HTTPException, status
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.security import create_access_token, get_current_user
from app.schemas.auth import CurrentUser, TokenRequest
from app.services.auth_service import RoleNotFoundError, verify_and_save_user

router = APIRouter(prefix="/auth", tags=["auth"])


def _verify_microsoft_token(token: str, client_id: str) -> dict:
    jwks_uri = "https://login.microsoftonline.com/common/discovery/v2.0/keys"
    jwks = http_requests.get(jwks_uri, timeout=10).json()
    return jwt.decode(token, jwks, algorithms=["RS256"], audience=client_id)


@router.post("/google/mobile-login")
def google_mobile_login(request_data: TokenRequest, db: Session = Depends(get_db)):
    client_id = settings.GOOGLE_CLIENT_ID

    try:
        idinfo = id_token.verify_oauth2_token(
            request_data.token, google_requests.Request(), client_id
        )

        email = idinfo.get("email")
        if not email or not email.endswith("@itmexicali.edu.mx"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "Acceso denegado. Se requiere correo institucional "
                    "(@itmexicali.edu.mx)"
                ),
            )
    except ValueError as err:
        raise HTTPException(status_code=401, detail="Token de Google inválido") from err

    try:
        user = verify_and_save_user(
            db=db,
            email=email,
            name=idinfo.get("name", "Estudiante ITM"),
            oauth_provider="google",
            oauth_sub=idinfo.get("sub"),
        )
    except RoleNotFoundError as err:
        raise HTTPException(status_code=500, detail=str(err)) from err

    access_token = create_access_token(data={"sub": str(user.id)})
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {"id": user.id, "email": user.email, "name": user.name},
    }


@router.post("/microsoft/mobile-login")
def microsoft_mobile_login(request_data: TokenRequest, db: Session = Depends(get_db)):
    try:
        claims = _verify_microsoft_token(
            request_data.token, settings.MICROSOFT_CLIENT_ID
        )
        email = claims.get("email")
        if not email or not email.endswith("@mexicali.tecnm.mx"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "Acceso denegado. Se requiere correo institucional "
                    "(@mexicali.tecnm.mx)"
                ),
            )
    except JWTError as err:
        raise HTTPException(
            status_code=401, detail="Token de Microsoft inválido"
        ) from err

    try:
        user = verify_and_save_user(
            db=db,
            email=email,
            name=claims.get("name", "Estudiante TecNM"),
            oauth_provider="microsoft",
            oauth_sub=claims.get("sub"),
        )
    except RoleNotFoundError as err:
        raise HTTPException(status_code=500, detail=str(err)) from err

    access_token = create_access_token(data={"sub": str(user.id)})
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {"id": user.id, "email": user.email, "name": user.name},
    }


@router.get("/me")
def read_users_me(current_user: CurrentUser = Depends(get_current_user)):
    """
    Devuelve los datos del usuario actual autenticado.
    """
    return {"id": current_user.id, "role": current_user.role}
