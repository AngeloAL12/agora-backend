from fastapi import APIRouter, Depends

from app.core.security import get_current_user, require_admin, require_staff
from app.schemas.auth import CurrentUser

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me")
def me(user: CurrentUser = Depends(get_current_user)):
    return user


@router.get("/admin")
def admin(user: CurrentUser = Depends(require_admin)):
    return {"message": "admin access", "user": user}


@router.get("/staff")
def staff(user: CurrentUser = Depends(require_staff)):
    return {"message": "staff access", "user": user}
