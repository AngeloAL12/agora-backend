from datetime import UTC, datetime, timedelta

import requests as http_requests
from fastapi import APIRouter, Depends, HTTPException, status
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from jose import JWTError, jwt
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.security import (
    TokenDecodeError,
    create_access_token,
    create_refresh_token,
    decode_token,
    get_current_user,
)
from app.models.auth.user_session import UserSession
from app.schemas.auth.auth import CurrentUser, TokenRequest
from app.services.auth.auth_service import RoleNotFoundError, verify_and_save_user

router = APIRouter(prefix="/auth", tags=["auth"])


def _save_refresh_token(db: Session, user_id: int, refresh_token: str) -> None:
    now = datetime.now(UTC)
    expires = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

    session = db.execute(
        select(UserSession).where(UserSession.id_user == user_id)
    ).scalar_one_or_none()

    if session:
        session.refresh_token = refresh_token
        session.last_active_at = now
        session.expires_at = expires
    else:
        session = UserSession(
            id_user=user_id,
            refresh_token=refresh_token,
            last_active_at=now,
            expires_at=expires,
        )
        db.add(session)

    db.commit()


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
async def google_mobile_login(
    request_data: TokenRequest,
    db: Session = Depends(get_db),
):
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
            photo=idinfo.get("picture"),
            oauth_provider="google",
            oauth_sub=idinfo.get("sub") or "",
        )
    except RoleNotFoundError as err:
        raise HTTPException(status_code=500, detail=str(err)) from err

    access_token = create_access_token(data={"sub": str(user.id)})
    refresh_token = create_refresh_token(data={"sub": str(user.id)})
    _save_refresh_token(db, user.id, refresh_token)
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "id_career": user.id_career,
        },
    }


@router.post("/microsoft/mobile-login")
async def microsoft_mobile_login(
    request_data: TokenRequest,
    db: Session = Depends(get_db),
):
    try:
        claims = _verify_microsoft_token(
            request_data.token,
            settings.MICROSOFT_CLIENT_ID,
            settings.MICROSOFT_TENANT_ID,
        )
        email = (
            claims.get("preferred_username") or claims.get("email") or claims.get("upn")
        )
        if not email:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Acceso denegado. No se encontró un correo válido.",
            )
        if not email.endswith("@mexicali.tecnm.mx"):
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
            photo=claims.get("picture"),
            oauth_provider="microsoft",
            oauth_sub=claims.get("sub") or "",
        )
    except RoleNotFoundError as err:
        raise HTTPException(status_code=500, detail=str(err)) from err

    access_token = create_access_token(data={"sub": str(user.id)})
    refresh_token = create_refresh_token(data={"sub": str(user.id)})
    _save_refresh_token(db, user.id, refresh_token)
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "id_career": user.id_career,
        },
    }


class RefreshRequest(BaseModel):
    refresh_token: str


@router.post("/refresh")
def refresh_access_token(request_data: RefreshRequest, db: Session = Depends(get_db)):
    try:
        payload = decode_token(request_data.refresh_token)
    except TokenDecodeError as err:
        raise HTTPException(status_code=401, detail="Refresh token inválido") from err

    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Refresh token inválido")

    user_id_str = payload.get("sub")
    if not user_id_str:
        raise HTTPException(status_code=401, detail="Refresh token inválido")

    try:
        user_id = int(user_id_str)
    except (TypeError, ValueError) as err:
        raise HTTPException(status_code=401, detail="Refresh token inválido") from err

    session = db.execute(
        select(UserSession).where(UserSession.id_user == user_id)
    ).scalar_one_or_none()

    if not session or session.refresh_token != request_data.refresh_token:
        raise HTTPException(status_code=401, detail="Refresh token inválido o revocado")

    new_access_token = create_access_token(data={"sub": str(user_id)})
    new_refresh_token = create_refresh_token(data={"sub": str(user_id)})
    now = datetime.now(UTC)
    session.refresh_token = new_refresh_token
    session.last_active_at = now
    session.expires_at = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    db.commit()

    return {
        "access_token": new_access_token,
        "refresh_token": new_refresh_token,
        "token_type": "bearer",
    }


@router.post("/logout")
def logout(
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    session = db.execute(
        select(UserSession).where(UserSession.id_user == current_user.id)
    ).scalar_one_or_none()

    if session:
        session.refresh_token = None
        db.commit()

    return {"message": "Sesión cerrada correctamente"}


@router.get("/dev-token")
def get_dev_token(user_id: str = "1", testing_secret: str | None = None):
    """
    Endpoint para obtener un token directamente.
    En "development" es de acceso libre.
    En "production" requiere pasar el `testing_secret` correcto.
    """
    if settings.ENV != "development":
        if (
            not settings.API_TESTING_SECRET
            or testing_secret != settings.API_TESTING_SECRET
        ):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Not found",
            )

    access_token = create_access_token(data={"sub": user_id})
    return {"access_token": access_token, "token_type": "bearer"}
