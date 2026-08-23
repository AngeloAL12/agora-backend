import secrets
from datetime import UTC, datetime
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
from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.core.database import get_db
from app.core.security import (
    _auth_user_cache_key,
    get_current_user,
    require_admin,
    require_staff,
)
from app.models.auth.user import User
from app.models.auth.user_session import UserSession
from app.models.career import Career
from app.models.club.club import Club
from app.models.club.club_join_request import ClubJoinRequest
from app.models.club.club_member import ClubMember
from app.models.club.event import ClubEvent
from app.models.club.message import ClubMessage
from app.models.club.post import ClubPost
from app.models.club.post_comment import ClubPostComment
from app.models.club.post_image import ClubPostImage
from app.models.club.post_like import ClubPostLike
from app.models.moderation.user_block import UserBlock
from app.models.notification.notification import Notification
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


class UserActiveRequest(BaseModel):
    is_active: bool


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
    response: Response,
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
    cache_service.delete(_user_me_cache_key(current_user.id))
    cache_service.delete(_auth_user_cache_key(current_user.id))
    db.refresh(user)
    response.headers["X-Cache"] = "BYPASS"
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
    cache_service.delete(_auth_user_cache_key(current_user.id))
    return {"id_career": user.id_career}


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_my_account(
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete personal content and anonymize records retained for audit purposes."""
    user = db.execute(
        select(User).where(User.id == current_user.id)
    ).scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado",
        )

    post_ids = list(
        db.execute(select(ClubPost.id).where(ClubPost.id_author == user.id)).scalars()
    )
    post_image_keys = (
        list(
            db.execute(
                select(ClubPostImage.url).where(ClubPostImage.id_post.in_(post_ids))
            ).scalars()
        )
        if post_ids
        else []
    )

    public_object_keys = [user.photo, *post_image_keys]
    for object_key in public_object_keys:
        if object_key and not object_key.startswith(("http://", "https://")):
            await storage_service.delete_file(
                settings.R2_BUCKET_PUBLIC,
                object_key,
            )

    led_clubs = list(
        db.execute(select(Club).where(Club.id_leader == user.id)).scalars()
    )
    for club in led_clubs:
        successor_id = db.execute(
            select(ClubMember.id_user)
            .join(User, User.id == ClubMember.id_user)
            .where(
                ClubMember.id_club == club.id,
                ClubMember.id_user != user.id,
                User.is_active.is_(True),
            )
            .order_by(ClubMember.joined_at.asc(), ClubMember.id.asc())
            .limit(1)
        ).scalar_one_or_none()
        if successor_id is None:
            club.archived_at = datetime.now(UTC)
        else:
            club.id_leader = successor_id

    # Social content and personal relationships are not retained.
    if post_ids:
        db.execute(delete(ClubPost).where(ClubPost.id.in_(post_ids)))
    db.execute(delete(ClubPostComment).where(ClubPostComment.id_user == user.id))
    db.execute(delete(ClubPostLike).where(ClubPostLike.id_user == user.id))
    db.execute(delete(ClubMessage).where(ClubMessage.id_user == user.id))
    db.execute(delete(ClubEvent).where(ClubEvent.id_author == user.id))
    db.execute(delete(ClubJoinRequest).where(ClubJoinRequest.id_user == user.id))
    db.execute(delete(ClubMember).where(ClubMember.id_user == user.id))
    db.execute(delete(Notification).where(Notification.id_user == user.id))
    db.execute(
        delete(UserBlock).where(
            (UserBlock.blocker_id == user.id) | (UserBlock.blocked_id == user.id)
        )
    )
    db.execute(delete(UserSession).where(UserSession.id_user == user.id))

    tombstone = secrets.token_urlsafe(18)
    user.email = f"deleted-{user.id}-{tombstone}@deleted.invalid"
    user.oauth_provider = "deleted"
    user.oauth_sub = tombstone
    user.name = "Cuenta eliminada"
    user.photo = None
    user.id_career = None
    user.is_active = False

    db.commit()

    cache_service.delete(_user_me_cache_key(user.id))
    cache_service.delete(_auth_user_cache_key(user.id))

    return Response(status_code=status.HTTP_204_NO_CONTENT)


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


@router.patch("/{user_id}/active")
def set_user_active(
    user_id: int,
    body: UserActiveRequest,
    _: CurrentUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Activa o desactiva un usuario. Solo accesible por admin.
    Invalida las entradas de cache de auth y perfil del usuario afectado.
    """
    user = db.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado",
        )
    user.is_active = body.is_active
    db.commit()
    cache_service.delete(_auth_user_cache_key(user_id))
    cache_service.delete(_user_me_cache_key(user_id))
    return {"id": user_id, "is_active": user.is_active}
