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
        "likes_count": 0,  # TODO: Not yet implemented
        "career": user.career.name if user.career else None,
        "photo": user.photo,
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

    previous_photo = user.photo
    if photo is not None:
        object_key = await storage_service.upload_file(
            photo,
            settings.R2_BUCKET_PUBLIC,
            f"users/{user.id}/photo",
        )
        base_public_url = (
            settings.R2_PUBLIC_URL
            if settings.R2_PUBLIC_URL
            else f"{settings.R2_ENDPOINT}/{settings.R2_BUCKET_PUBLIC}"
        )
        # Ensure no trailing slash before appending object_key
        base_public_url = base_public_url.rstrip("/")
        user.photo = f"{base_public_url}/{object_key}"

    db.commit()
    db.refresh(user)

    if photo is not None and previous_photo:
        old_key = None
        if settings.R2_PUBLIC_URL and previous_photo.startswith(
            f"{settings.R2_PUBLIC_URL.rstrip('/')}/"
        ):
            old_key = previous_photo.split(f"{settings.R2_PUBLIC_URL.rstrip('/')}/", 1)[
                1
            ]
        elif previous_photo.startswith(
            f"{settings.R2_ENDPOINT}/{settings.R2_BUCKET_PUBLIC}/"
        ):
            old_key = previous_photo.split(
                f"{settings.R2_ENDPOINT}/{settings.R2_BUCKET_PUBLIC}/", 1
            )[1]

        if old_key:
            await storage_service.delete_file(settings.R2_BUCKET_PUBLIC, old_key)

    return {
        "id": user.id,
        "email": user.email,
        "role": current_user.role,
        "name": user.name,
        "clubs_count": len(user.club_memberships),
        "complaints_count": len(user.complaints),
        "likes_count": 0,
        "career": user.career.name if user.career else None,
        "photo": user.photo,
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
