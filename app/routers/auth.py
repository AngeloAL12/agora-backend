from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import create_access_token
from app.models.auth.role import Role
from app.models.auth.user import User

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: EmailStr
    name: str
    photo: str | None = None
    oauth_provider: str
    oauth_sub: str


@router.post("/login")
def login(data: LoginRequest, db: Session = Depends(get_db)):
    user = (
        db.query(User)
        .filter(
            User.oauth_provider == data.oauth_provider,
            User.oauth_sub == data.oauth_sub,
        )
        .first()
    )

    if not user:
        default_role = db.query(Role).filter(Role.name == "user").first()

        if not default_role:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="No existe el rol base 'user' en la base de datos",
            )

        user = User(
            email=data.email,
            oauth_provider=data.oauth_provider,
            oauth_sub=data.oauth_sub,
            name=data.name,
            photo=data.photo,
            id_role=default_role.id,
            is_active=True,
        )

        db.add(user)

        try:
            db.commit()
            db.refresh(user)
        except IntegrityError as e:
            db.rollback()
            user = (
                db.query(User)
                .filter(
                    User.oauth_provider == data.oauth_provider,
                    User.oauth_sub == data.oauth_sub,
                )
                .first()
            )
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="No se pudo crear u obtener el usuario",
                ) from e

    else:
        updated = False

        if user.email != data.email:
            user.email = data.email
            updated = True

        if user.name != data.name:
            user.name = data.name
            updated = True

        if user.photo != data.photo:
            user.photo = data.photo
            updated = True

        if updated:
            db.commit()
            db.refresh(user)

    token = create_access_token({"sub": str(user.id)})

    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "role": user.role.name,
            "is_active": user.is_active,
        },
    }
