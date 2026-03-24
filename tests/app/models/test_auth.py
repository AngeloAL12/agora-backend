from app.models.auth import Role, StaffWhitelist, User, UserSession


def test_create_role(db):
    role = Role(name="admin")
    db.add(role)
    db.commit()
    db.refresh(role)

    assert role.id is not None
    assert role.name == "admin"


def test_create_user(db):
    role = Role(name="student")
    db.add(role)
    db.commit()
    db.refresh(role)

    user = User(
        email="user@example.com",
        oauth_provider="google",
        oauth_sub="google-sub-123",
        name="Test User",
        photo="https://example.com/photo.jpg",
        id_role=role.id,
        id_career=42,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    assert user.id is not None
    assert user.id_role == role.id
    assert user.role.name == "student"
    assert user.created_at is not None
    assert user.updated_at is not None


def test_create_staff_whitelist(db):
    role = Role(name="staff")
    db.add(role)
    db.commit()
    db.refresh(role)

    whitelisted = StaffWhitelist(email="staff@example.com", id_role=role.id)
    db.add(whitelisted)
    db.commit()
    db.refresh(whitelisted)

    assert whitelisted.id is not None
    assert whitelisted.role.name == "staff"


def test_create_user_session(db):
    role = Role(name="member")
    db.add(role)
    db.commit()
    db.refresh(role)

    user = User(
        email="member@example.com",
        oauth_provider="github",
        oauth_sub="github-sub-123",
        name="Member User",
        id_role=role.id,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    session = UserSession(id_user=user.id, token_version=2, push_token="push-token-abc")
    db.add(session)
    db.commit()
    db.refresh(session)

    assert session.id is not None
    assert session.user.email == "member@example.com"
    assert session.created_at is not None
