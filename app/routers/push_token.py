from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.auth.user import User  # <-- importa el modelo User
from app.models.auth.user_session import UserSession
from app.schemas.push_token import PushTokenRequest

router = APIRouter()


@router.post("/push-token")
def save_push_token(request: PushTokenRequest, db: Session = Depends(get_db)):
    # 1. Validar que el usuario exista
    user = db.query(User).filter_by(id=request.user_id).first()
    if not user:
        return {"error": f"Usuario con id {request.user_id} no existe"}

    # 2. Buscar si ya tiene sesión
    session = db.query(UserSession).filter_by(id_user=request.user_id).first()
    if session:
        session.push_token = request.push_token
        session.created_at = datetime.utcnow()
    else:
        session = UserSession(
            id_user=request.user_id,
            push_token=request.push_token,
            created_at=datetime.utcnow(),
        )
        db.add(session)

    db.commit()
    return {"message": "Push token guardado correctamente"}
