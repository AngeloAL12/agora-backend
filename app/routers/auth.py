import os

import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from jwt import PyJWKClient
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import create_access_token, get_current_user
from app.models.auth.user import User

router = APIRouter(prefix="/auth", tags=["auth"])

class TokenRequest(BaseModel):
    token: str

def verify_and_save_user(
    email: str, name: str, oauth_provider: str, oauth_sub: str, db: Session
):
    user = db.query(User).filter(
        User.oauth_provider == oauth_provider, 
        User.oauth_sub == oauth_sub
    ).first()

    if not user:
        user = User(
            email=email,
            name=name,
            oauth_provider=oauth_provider, 
            oauth_sub=oauth_sub,
            id_role=1, 
            is_active=True
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    return user

@router.post("/google/mobile-login")
def google_mobile_login(request_data: TokenRequest, db: Session = Depends(get_db)):
    google_client_id = os.getenv("GOOGLE_CLIENT_ID")
    try:
        idinfo = id_token.verify_oauth2_token(
            request_data.token, 
            google_requests.Request(), 
            google_client_id
        )
        email = idinfo.get("email")
        if not email or not email.endswith("@itmexicali.edu.mx"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Acceso denegado. Google requiere correo @itmexicali.edu.mx"
            )
    except ValueError as err:
        raise HTTPException(
            status_code=401, detail="Token de Google inválido"
        ) from err

    user = verify_and_save_user(
        email=email,
        name=idinfo.get("name", "Estudiante ITM"),
        oauth_provider="google",
        oauth_sub=idinfo.get("sub"),
        db=db
    )
    access_token = create_access_token(data={"sub": user.email})
    return {
        "access_token": access_token, 
        "token_type": "bearer", 
        "user": {"id": user.id, "email": user.email, "name": user.name}
    }

@router.post("/microsoft/mobile-login")
def microsoft_mobile_login(request_data: TokenRequest, db: Session = Depends(get_db)):
    microsoft_client_id = os.getenv("MICROSOFT_CLIENT_ID")
    try:
        jwks_url = "https://login.microsoftonline.com/common/discovery/v2.0/keys"
        jwks_client = PyJWKClient(jwks_url)
        signing_key = jwks_client.get_signing_key_from_jwt(request_data.token)
        idinfo = jwt.decode(
            request_data.token,
            signing_key.key,
            algorithms=["RS256"],
            audience=microsoft_client_id,
            options={"verify_iss": False}
        )
        email = idinfo.get("email") or idinfo.get("preferred_username")
        if not email or not email.endswith("@mexicali.tecnm.mx"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Acceso denegado. Microsoft requiere correo @mexicali.tecnm.mx"
            )
    except Exception as err:
        raise HTTPException(
            status_code=401, 
            detail="Token de Microsoft inválido o dominio no permitido"
        ) from err

    user = verify_and_save_user(
        email=email,
        name=idinfo.get("name", "Estudiante TecNM"),
        oauth_provider="microsoft",
        oauth_sub=idinfo.get("sub"),
        db=db
    )
    access_token = create_access_token(data={"sub": user.email})
    return {
        "access_token": access_token, 
        "token_type": "bearer", 
        "user": {"id": user.id, "email": user.email, "name": user.name}
    }

@router.get("/me")
def read_users_me(current_user: User = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "name": current_user.name,
        "email": current_user.email,
        "role_id": current_user.id_role,
        "provider": current_user.oauth_provider
    }