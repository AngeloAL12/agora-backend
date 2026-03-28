import pytest
from fastapi import HTTPException

from app.models.auth.role import Role
from app.models.auth.user import User
from app.services.auth_service import verify_and_save_user


def test_verify_and_save_user_new(db):
    """Prueba que un usuario nuevo se guarde correctamente en la BD"""
    if not db.query(Role).filter(Role.name == "user").first():
        db.add(Role(name="user"))
        db.commit()

    user = verify_and_save_user(
        db=db,
        email="nuevo@itmexicali.edu.mx",
        name="Nuevo Usuario",
        oauth_provider="google",
        oauth_sub="sub-nuevo",
    )

    assert user.id is not None
    assert user.email == "nuevo@itmexicali.edu.mx"


def test_verify_and_save_user_existing(db):
    """Prueba que si el usuario ya existe, no se duplique"""
    if not db.query(Role).filter(Role.name == "user").first():
        db.add(Role(name="user"))
        db.commit()

    # Creamos el usuario la primera vez
    verify_and_save_user(
        db=db,
        email="existe@itmexicali.edu.mx",
        name="Usuario Existente",
        oauth_provider="google",
        oauth_sub="sub-existe",
    )

    # Lo volvemos a llamar (simulando un segundo login)
    user_second_time = verify_and_save_user(
        db=db,
        email="existe@itmexicali.edu.mx",
        name="Usuario Existente",
        oauth_provider="google",
        oauth_sub="sub-existe",
    )

    # Verificamos que solo haya 1 en la base de datos con ese sub
    count = db.query(User).filter(User.oauth_sub == "sub-existe").count()
    assert count == 1
    assert user_second_time.email == "existe@itmexicali.edu.mx"


def test_verify_and_save_user_missing_role(db):
    """Prueba que lance error 500 si el rol 'user' no existe en la BD"""
    # Nos aseguramos de borrar el rol 'user' si existe
    db.query(Role).filter(Role.name == "user").delete()
    db.commit()

    with pytest.raises(HTTPException) as exc_info:
        verify_and_save_user(
            db=db,
            email="fallo@itmexicali.edu.mx",
            name="Usuario Fallo",
            oauth_provider="google",
            oauth_sub="sub-fallo",
        )

    assert exc_info.value.status_code == 500
