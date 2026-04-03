import requests as http_requests
from fastapi import APIRouter, Depends, HTTPException, status
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.security import create_access_token, get_current_user
from app.schemas.auth.auth import CurrentUser, TokenRequest
from app.services.auth.auth_service import RoleNotFoundError, verify_and_save_user

router = APIRouter(prefix="/auth", tags=["auth"])


def _normalize_google_client_id(client_id: str) -> str:
    if client_id.startswith("com.googleusercontent.apps."):
        suffix = client_id.removeprefix("com.googleusercontent.apps.")
        return f"{suffix}.apps.googleusercontent.com"

    return client_id


def _verify_microsoft_token(token: str, client_id: str, tenant_id: str) -> dict:
    jwks_uri = f"https://login.microsoftonline.com/{tenant_id}/discovery/v2.0/keys"
    jwks = http_requests.get(jwks_uri, timeout=10).json()
    return jwt.decode(
        token,
        jwks,
        algorithms=["RS256"],
        audience=client_id,
        options={"verify_iss": False},
    )


@router.post("/google/mobile-login")
def google_mobile_login(request_data: TokenRequest, db: Session = Depends(get_db)):
    # Acepta los client IDs configurados para Web, iOS y Android.
    valid_client_ids = [
        _normalize_google_client_id(cid)
        for cid in [
            settings.GOOGLE_CLIENT_ID,
            settings.GOOGLE_IOS_CLIENT_ID,
            settings.GOOGLE_ANDROID_CLIENT_ID,
        ]
        if cid
    ]

    try:
        idinfo = id_token.verify_oauth2_token(
            request_data.token, google_requests.Request(), None
        )
    except ValueError as err:
        raise HTTPException(status_code=401, detail="Token de Google inválido") from err

    # Validate audience first
    token_aud = _normalize_google_client_id(idinfo.get("aud") or "")
    if valid_client_ids and token_aud not in valid_client_ids:
        raise HTTPException(status_code=401, detail="Token de Google inválido")

    email = idinfo.get("email")
    if not email or not email.endswith("@itmexicali.edu.mx"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Acceso denegado. Se requiere correo institucional (@itmexicali.edu.mx)"
            ),
        )

    try:
        user = verify_and_save_user(
            db=db,
            email=email,
            name=idinfo.get("name", "Estudiante ITM"),
            oauth_provider="google",
            oauth_sub=idinfo.get("sub") or "",
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
            request_data.token,
            settings.MICROSOFT_CLIENT_ID,
            settings.MICROSOFT_TENANT_ID,
        )
        email = (
            claims.get("preferred_username") or claims.get("email") or claims.get("upn")
        )
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
            oauth_sub=claims.get("sub") or "",
        )
    except RoleNotFoundError as err:
        raise HTTPException(status_code=500, detail=str(err)) from err

    access_token = create_access_token(data={"sub": str(user.id)})
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {"id": user.id, "email": user.email, "name": user.name},
    }


@router.post("/test-login")
def test_login(db: Session = Depends(get_db)):
    """
    Endpoint de prueba para desarrollo. Crea/obtiene un usuario de prueba
    y devuelve un access token válido sin requerir OAuth.
    
    Solo disponible en ambiente de desarrollo.
    """
    email = "test@itmexicali.edu.mx"
    try:
        user = verify_and_save_user(
            db=db,
            email=email,
            name="Usuario Prueba",
            oauth_provider="test",
            oauth_sub="test-user-123",
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
