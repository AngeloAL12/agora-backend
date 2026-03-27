from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.auth import get_current_user
from app.models.auth.user import User
from app.models.auth.user_session import UserSession
from app.schemas.push_token import PushTokenRequest

router = APIRouter()

@router.post("/push-token")
def save_push_token(
    payload: PushTokenRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    session = db.query(UserSession).filter(UserSession.id_user == current_user.id).first()
    now = datetime.now(timezone.utc)

    if session:
        session.push_token = payload.push_token

    else:
        session = UserSession(
            id_user=current_user.id,
            push_token=payload.push_token,
            created_at=now,
        )
        db.add(session)

    db.commit()
    return {"message": "Push token guardado correctamente"}