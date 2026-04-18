from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.auth.role import Role
from app.models.auth.user import User


class RoleNotFoundError(Exception):
    """Raised when the 'user' role does not exist in the database."""


def format_user_name(raw_name: str) -> str:
    if not raw_name:
        return ""
    name = raw_name.rstrip(" _\t\n\r")
    words = name.split()
    return " ".join([w.capitalize() for w in words])


def verify_and_save_user(
    db: Session,
    email: str,
    name: str,
    oauth_provider: str,
    oauth_sub: str,
    photo: str | None = None,
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

    if getattr(user, "email", None) != email and not user:
        # Si no se encuentra por provider/sub, buscar por email para enlazar cuentas
        user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()

    if user:
        # Actualiza los datos con la info más reciente del proveedor de identidad
        user.email = email
        user.oauth_provider = oauth_provider
        user.oauth_sub = oauth_sub

        if not user.name:
            user.name = format_user_name(name)

        if not user.photo and photo:
            user.photo = photo

        db.commit()
        db.refresh(user)
    else:
        # Crear usuario nuevo
        student_role = db.execute(
            select(Role).where(Role.name == "user")
        ).scalar_one_or_none()

        if not student_role:
            raise RoleNotFoundError(
                "Error de configuración: El rol 'user' no existe en la base de datos"
            )

        user = User(
            email=email,
            name=format_user_name(name),
            photo=photo,
            oauth_provider=oauth_provider,
            oauth_sub=oauth_sub,
            id_role=student_role.id,
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    return user
