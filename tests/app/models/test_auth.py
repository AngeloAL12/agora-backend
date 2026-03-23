from datetime import datetime, timedelta

from app.models.auth import Role, StaffWhitelist, User, UserSession


def test_create_role(db):
    role = Role(name="admin", description="Administrator role")
    db.add(role)
    db.commit()
    db.refresh(role)

    assert role.id is not None
    assert role.name == "admin"
    assert role.description == "Administrator role"


def test_create_user(db):
    role = Role(name="editor")
    db.add(role)
    db.commit()

    user = User(
        email="user@example.com",
        hashed_password="hashed_pw",
        is_active=True,
        role_id=role.id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    assert user.id is not None
    assert user.email == "user@example.com"
    assert user.is_active is True
    assert user.role_id == role.id


def test_user_without_role(db):
    user = User(email="norole@example.com", hashed_password="pw")
    db.add(user)
    db.commit()
    db.refresh(user)

    assert user.role_id is None


def test_create_user_session(db):
    user = User(email="session@example.com", hashed_password="pw")
    db.add(user)
    db.commit()

    expires = datetime.utcnow() + timedelta(hours=1)
    session = UserSession(
        user_id=user.id,
        token="sometoken123",
        expires_at=expires,
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    assert session.id is not None
    assert session.user_id == user.id
    assert session.token == "sometoken123"


def test_create_staff_whitelist(db):
    entry = StaffWhitelist(email="staff@example.com")
    db.add(entry)
    db.commit()
    db.refresh(entry)

    assert entry.id is not None
    assert entry.email == "staff@example.com"
