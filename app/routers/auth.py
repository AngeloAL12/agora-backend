import os
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel

# Librerías para Google y Microsoft
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
import jwt
from jwt import PyJWKClient

# Importaciones de tu proyecto
from app.core.database import get_db 
from app.models.auth.user import User 
from app.core.security import create_access_token, get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])

class TokenRequest(BaseModel):
    token: str

# --- FUNCIÓN AUXILIAR DE REGISTRO ---
def verify_and_save_user(email: str, name: str, oauth_provider: str, oauth_sub: str, db: Session):
    # 1. Buscar si el usuario ya existe
    user = db.query(User).filter(
        User.oauth_provider == oauth_provider, 
        User.oauth_sub == oauth_sub
    ).first()

    # 2. Si no existe, lo registramos
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

# --- ENDPOINT 1: GOOGLE (Solo @itmexicali.edu.mx) ---
@router.post("/google/mobile-login")
def google_mobile_login(request_data: TokenRequest, db: Session = Depends(get_db)):
    GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
    
    try:
        idinfo = id_token.verify_oauth2_token(
            request_data.token, 
            google_requests.Request(), 
            GOOGLE_CLIENT_ID
        )
        email = idinfo.get("email")

        # VALIDACIÓN ESPECÍFICA PARA GOOGLE
        if not email or not email.endswith("@itmexicali.edu.mx"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Acceso denegado. Google requiere correo @itmexicali.edu.mx"
            )

    except ValueError:
        raise HTTPException(status_code=401, detail="Token de Google inválido")

    user = verify_and_save_user(
        email=email,
        name=idinfo.get("name", "Estudiante ITM"),
        oauth_provider="google",
        oauth_sub=idinfo.get("sub"),
        db=db
    )

    access_token = create_access_token(data={"sub": user.email})
    return {"access_token": access_token, "token_type": "bearer", "user": {"id": user.id, "email": user.email, "name": user.name}}

# --- ENDPOINT 2: MICROSOFT (Solo @mexicali.tecnm.mx) ---
@router.post("/microsoft/mobile-login")
def microsoft_mobile_login(request_data: TokenRequest, db: Session = Depends(get_db)):
    MICROSOFT_CLIENT_ID = os.getenv("MICROSOFT_CLIENT_ID")
    
    try:
        jwks_url = "https://login.microsoftonline.com/common/discovery/v2.0/keys"
        jwks_client = PyJWKClient(jwks_url)
        signing_key = jwks_client.get_signing_key_from_jwt(request_data.token)

        idinfo = jwt.decode(
            request_data.token,
            signing_key.key,
            algorithms=["RS256"],
            audience=MICROSOFT_CLIENT_ID,
            options={"verify_iss": False}
        )
        email = idinfo.get("email") or idinfo.get("preferred_username")

        # VALIDACIÓN ESPECÍFICA PARA MICROSOFT
        if not email or not email.endswith("@mexicali.tecnm.mx"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Acceso denegado. Microsoft requiere correo @mexicali.tecnm.mx"
            )

    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Token de Microsoft inválido o dominio no permitido")

    user = verify_and_save_user(
        email=email,
        name=idinfo.get("name", "Estudiante TecNM"),
        oauth_provider="microsoft",
        oauth_sub=idinfo.get("sub"),
        db=db
    )

    access_token = create_access_token(data={"sub": user.email})
    return {"access_token": access_token, "token_type": "bearer", "user": {"id": user.id, "email": user.email, "name": user.name}}

# --- RUTA DE PERFIL (PROTEGIDA) ---
@router.get("/me")
def read_users_me(current_user: User = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "name": current_user.name,
        "email": current_user.email,
        "role_id": current_user.id_role,
        "provider": current_user.oauth_provider
    }