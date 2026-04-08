from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.database import get_db
from app.core.security import get_current_user, require_admin, require_staff
from app.models.auth.user import User
from app.models.career import Career
from app.schemas.auth.auth import CurrentUser

router = APIRouter(prefix="/users", tags=["users"])


class CareerUpdateRequest(BaseModel):
    career_id: int


class UserMeResponse(BaseModel):
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
        "name": user.name,
        "clubs_count": len(user.club_memberships),
        "complaints_count": len(user.complaints),
        "likes_count": 0,  # TODO: Not yet implemented
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


@router.get("/admin")
def admin(user: CurrentUser = Depends(require_admin)):
    return {"message": "admin access", "user": user}


@router.get("/staff")
def staff(user: CurrentUser = Depends(require_staff)):
    return {"message": "staff access", "user": user}
