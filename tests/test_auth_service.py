import pytest
from sqlalchemy import select

from app.models.auth.user import User
from app.services.auth.auth_service import RoleNotFoundError, verify_and_save_user


def test_verify_and_save_user_new(db, user_role):
    """Prueba que un usuario nuevo se guarde correctamente en la BD"""
    user = verify_and_save_user(
        db=db,
        email="nuevo@itmexicali.edu.mx",
        name="Nuevo Usuario",
        oauth_provider="google",
        oauth_sub="sub-nuevo",
    )

    assert user.id is not None
    assert user.email == "nuevo@itmexicali.edu.mx"


def test_verify_and_save_user_existing(db, user_role):
    """Prueba que si el usuario ya existe, no se duplique"""
    verify_and_save_user(
        db=db,
        email="existe@itmexicali.edu.mx",
        name="Usuario Existente",
        oauth_provider="google",
        oauth_sub="sub-existe",
    )

    user_second_time = verify_and_save_user(
        db=db,
        email="existe@itmexicali.edu.mx",
        name="Usuario Existente",
        oauth_provider="google",
        oauth_sub="sub-existe",
    )

    count = (
        db.execute(select(User).where(User.oauth_sub == "sub-existe")).scalars().all()
    )
    assert len(count) == 1
    assert user_second_time.email == "existe@itmexicali.edu.mx"


def test_verify_and_save_user_missing_role(db):
    """Prueba que lance RoleNotFoundError si el rol 'user' no existe en la BD"""
    from sqlalchemy import delete

    from app.models.auth.role import Role

    db.execute(delete(Role).where(Role.name == "user"))
    db.commit()

    with pytest.raises(RoleNotFoundError):
        verify_and_save_user(
            db=db,
            email="fallo@itmexicali.edu.mx",
            name="Usuario Fallo",
            oauth_provider="google",
            oauth_sub="sub-fallo",
        )
