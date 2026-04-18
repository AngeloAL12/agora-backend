from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.auth.user import User
from app.models.career import Career
from app.schemas.auth.auth import CurrentUser
from app.services.storage_service import storage_service

router = APIRouter(prefix="/users", tags=["users"])


def _photo_url(object_key: str | None) -> str | None:
    if not object_key:
        return None
    base = (
        settings.R2_PUBLIC_URL or f"{settings.R2_ENDPOINT}/{settings.R2_BUCKET_PUBLIC}"
    ).rstrip("/")
    return f"{base}/{object_key}"


class CareerUpdateRequest(BaseModel):
    career_id: int


class UserMeResponse(BaseModel):
    id: int
    email: str
    role: str
    name: str
    clubs_count: int
    complaints_count: int
    likes_count: int
    career: str | None
    photo: str | None


@router.get("/me", response_model=UserMeResponse)
def me(
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user = db.execute(
        select(User)
        .options(
            selectinload(User.career),
            selectinload(User.club_memberships),
            selectinload(User.complaints),
        )
        .where(User.id == current_user.id)
    ).scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado",
        )

    return {
        "id": user.id,
        "email": user.email,
        "role": current_user.role,
        "name": user.name,
        "clubs_count": len(user.club_memberships),
        "complaints_count": len(user.complaints),
        "likes_count": 0,
        "career": user.career.name if user.career else None,
        "photo": _photo_url(user.photo),
    }


@router.patch("/me", response_model=UserMeResponse)
async def update_my_profile(
    name: str | None = Form(None),
    id_career: int | None = Form(None),
    photo: UploadFile | None = File(None),
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user = db.execute(
        select(User)
        .options(
            selectinload(User.career),
            selectinload(User.club_memberships),
            selectinload(User.complaints),
        )
        .where(User.id == current_user.id)
    ).scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado",
        )

    if id_career is not None:
        career = db.execute(
            select(Career).where(Career.id == id_career)
        ).scalar_one_or_none()
        if not career:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Carrera no encontrada",
            )
        user.id_career = id_career

    if name is not None:
        user.name = name.strip() or user.name

    previous_key = user.photo
    if photo is not None:
        user.photo = await storage_service.upload_file(
            photo,
            settings.R2_BUCKET_PUBLIC,
            f"users/{user.id}/photo",
        )

    db.commit()
    db.refresh(user)

    if photo is not None and previous_key:
        await storage_service.delete_file(settings.R2_BUCKET_PUBLIC, previous_key)

    return {
        "id": user.id,
        "email": user.email,
        "role": current_user.role,
        "name": user.name,
        "clubs_count": len(user.club_memberships),
        "complaints_count": len(user.complaints),
        "likes_count": 0,
        "career": user.career.name if user.career else None,
        "photo": _photo_url(user.photo),
    }


@router.patch("/me/career")
def update_my_career(
    body: CareerUpdateRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Asigna o actualiza la carrera del usuario autenticado.
    """
    career = db.execute(
        select(Career).where(Career.id == body.career_id)
    ).scalar_one_or_none()

    if not career:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Carrera no encontrada",
        )

    user = db.execute(
        select(User).where(User.id == current_user.id)
    ).scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado",
        )

    user.id_career = body.career_id
    db.commit()

    return {"id_career": user.id_career}
