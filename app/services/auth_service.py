from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.auth.role import Role
from app.models.auth.user import User


def verify_and_save_user(
    db: Session, email: str, name: str, oauth_provider: str, oauth_sub: str
):
    """
    Lógica de negocio para buscar un usuario existente o
    crear uno nuevo con el rol 'user'.
    """
    user = (
        db.query(User)
        .filter(User.oauth_provider == oauth_provider, User.oauth_sub == oauth_sub)
        .first()
    )

    if not user:
        # Buscamos el rol 'user' dinámicamente
        student_role = db.query(Role).filter(Role.name == "user").first()
        if not student_role:
            raise HTTPException(
                status_code=500,
                detail=(
                    "Error de configuración: El rol 'user' "
                    "no existe en la base de datos"
                ),
            )

        user = User(
            email=email,
            name=name,
            oauth_provider=oauth_provider,
            oauth_sub=oauth_sub,
            id_role=student_role.id,
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    return user
