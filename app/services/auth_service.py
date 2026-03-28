from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.auth.role import Role
from app.models.auth.user import User


class RoleNotFoundError(Exception):
    """Raised when the 'user' role does not exist in the database."""


def verify_and_save_user(
    db: Session, email: str, name: str, oauth_provider: str, oauth_sub: str
):
    """
    Lógica de negocio para buscar un usuario existente o
    crear uno nuevo con el rol 'user'.
    """
    user = db.execute(
        select(User).where(
            User.oauth_provider == oauth_provider,
            User.oauth_sub == oauth_sub,
        )
    ).scalar_one_or_none()

    if not user:
        student_role = db.execute(
            select(Role).where(Role.name == "user")
        ).scalar_one_or_none()

        if not student_role:
            raise RoleNotFoundError(
                "Error de configuración: El rol 'user' no existe en la base de datos"
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
