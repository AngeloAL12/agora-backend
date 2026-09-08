import pytest
from sqlalchemy import select

from app.models.auth.role import Role
from app.models.auth.user import User
from app.services.auth.auth_service import (
    RoleNotFoundError,
    format_user_name,
    verify_and_save_user,
)


def test_format_user_name_returns_empty_for_empty_value():
    assert format_user_name("") == ""


def test_format_user_name_trims_suffix_and_capitalizes_words():
    assert format_user_name("juan perez__ \n") == "Juan Perez"


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


def test_verify_and_save_user_links_existing_email_and_updates_missing_fields(
    db, user_role
):
    existing = User(
        email="linked@itmexicali.edu.mx",
        name="",
        photo=None,
        oauth_provider="google",
        oauth_sub="old-sub",
        id_role=user_role.id,
        is_active=True,
    )
    db.add(existing)
    db.commit()
    db.refresh(existing)

    user = verify_and_save_user(
        db=db,
        email="linked@itmexicali.edu.mx",
        name="linked user",
        oauth_provider="microsoft",
        oauth_sub="new-sub",
        photo="users/photo.png",
    )

    assert user.id == existing.id
    assert user.oauth_provider == "microsoft"
    assert user.oauth_sub == "new-sub"
    assert user.name == "Linked User"
    assert user.photo == "users/photo.png"


def test_verify_and_save_user_existing_keeps_name_and_photo_when_present(db, user_role):
    existing = User(
        email="keep@itmexicali.edu.mx",
        name="Keep Name",
        photo="existing/photo.png",
        oauth_provider="google",
        oauth_sub="keep-sub",
        id_role=user_role.id,
        is_active=True,
    )
    db.add(existing)
    db.commit()

    user = verify_and_save_user(
        db=db,
        email="keep@itmexicali.edu.mx",
        name="new ignored name",
        oauth_provider="google",
        oauth_sub="keep-sub",
        photo="new/photo.png",
    )

    assert user.name == "Keep Name"
    assert user.photo == "existing/photo.png"
