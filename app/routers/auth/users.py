from datetime import datetime
from typing import Any

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Response,
    UploadFile,
    status,
)
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.core.database import get_db
from app.core.security import get_current_user, require_admin, require_staff
from app.models.auth.user import User
from app.models.career import Career
from app.schemas.auth.auth import CurrentUser
from app.services.cache_service import cache_service
from app.services.storage_service import storage_service

router = APIRouter(prefix="/users", tags=["users"])


def _user_me_cache_key(user_id: int) -> str:
    return f"users:me:v1:{user_id}"


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


class UserListResponse(BaseModel):
    id: int
    email: str
    name: str
    photo: str | None
    is_active: bool
    id_role: int
    created_at: datetime | Any = Field(..., description="Creation timestamp")
    model_config = ConfigDict(from_attributes=True)


@router.get("/me", response_model=UserMeResponse)
def me(
    response: Response,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    cache_key = _user_me_cache_key(current_user.id)
    cached, cache_status = cache_service.get_json_with_status(cache_key)
    response.headers["X-Cache"] = cache_status.upper()
    if cached is not None:
        return cached

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
    payload = {
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
    cache_service.set_json(cache_key, payload, settings.USER_ME_CACHE_TTL_SECONDS)
    return payload


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
    cache_service.delete(_user_me_cache_key(current_user.id))
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
    cache_service.delete(_user_me_cache_key(current_user.id))
    return {"id_career": user.id_career}


@router.get("", response_model=list[UserListResponse])
def get_all_users(
    _: CurrentUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    users = db.execute(select(User).order_by(User.created_at.desc())).scalars().all()
    return users


@router.get("/admin")
def admin(user: CurrentUser = Depends(require_admin)):
    return {"message": "admin access", "user": user}


@router.get("/staff")
def staff(user: CurrentUser = Depends(require_staff)):
    return {"message": "staff access", "user": user}
