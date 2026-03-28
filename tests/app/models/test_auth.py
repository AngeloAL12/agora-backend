from app.models.auth import Role, StaffWhitelist, User, UserSession
from app.models.career import Career


def _persist_and_refresh(db, obj):
    """Helper para insertar y refrescar cualquier objeto en la sesión."""
    db.add(obj)
    db.commit()
    db.refresh(obj)


def test_create_role(db):
    role = Role(name="admin")
    _persist_and_refresh(db, role)

    assert role.id is not None
    assert role.name == "admin"


def test_create_user(db):
    role = Role(name="student")
    career = Career(name="Ing. Sistemas Computacionales")
    _persist_and_refresh(db, role)
    _persist_and_refresh(db, career)

    user = User(
        email="user@example.com",
        oauth_provider="google",
        oauth_sub="google-sub-123",
        name="Test User",
        photo="https://example.com/photo.jpg",
        id_role=role.id,
        id_career=career.id,
        is_active=True,
    )
    _persist_and_refresh(db, user)

    assert user.id is not None
    assert user.id_role == role.id
    assert user.id_career == career.id
    assert user.career is not None
    assert user.career.name == "Ing. Sistemas Computacionales"
    assert user.role.name == "student"
    assert user.created_at is not None
    assert user.updated_at is not None


def test_create_staff_whitelist(db):
    role = Role(name="staff")
    _persist_and_refresh(db, role)

    whitelisted = StaffWhitelist(email="staff@example.com", id_role=role.id)
    _persist_and_refresh(db, whitelisted)

    assert whitelisted.id is not None
    assert whitelisted.role.name == "staff"


def test_create_user_session(db):
    role = Role(name="member")
    _persist_and_refresh(db, role)

    user = User(
        email="member@example.com",
        oauth_provider="github",
        oauth_sub="github-sub-123",
        name="Member User",
        id_role=role.id,
        is_active=True,
    )
    _persist_and_refresh(db, user)

    session = UserSession(id_user=user.id, token_version=2, push_token="push-token-abc")
    _persist_and_refresh(db, session)

    assert session.id is not None
    assert session.user.email == "member@example.com"
    assert session.created_at is not None
