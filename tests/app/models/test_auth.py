from datetime import datetime

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.auth import Role, StaffWhitelist, User, UserSession


def test_create_role(db_session):
    """Test creating a Role model instance."""
    role = Role(id=1, name="admin")
    db_session.add(role)
    db_session.commit()

    saved_role = db_session.query(Role).filter_by(id=1).first()
    assert saved_role is not None
    assert saved_role.name == "admin"


def test_role_unique_name(db_session):
    """Test that role names must be unique."""
    role1 = Role(id=1, name="admin")
    role2 = Role(id=2, name="admin")

    db_session.add(role1)
    db_session.commit()

    db_session.add(role2)
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_create_user(db_session):
    """Test creating a User model instance."""
    # First create a role
    role = Role(id=1, name="user")
    db_session.add(role)
    db_session.commit()

    # Create user
    user = User(
        id=1,
        email="test@example.com",
        oauth_provider="google",
        oauth_sub="12345",
        name="Test User",
        photo="https://example.com/photo.jpg",
        id_role=1,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()

    saved_user = db_session.query(User).filter_by(id=1).first()
    assert saved_user is not None
    assert saved_user.email == "test@example.com"
    assert saved_user.oauth_provider == "google"
    assert saved_user.oauth_sub == "12345"
    assert saved_user.name == "Test User"
    assert saved_user.photo == "https://example.com/photo.jpg"
    assert saved_user.id_role == 1
    assert saved_user.is_active is True
    assert saved_user.created_at is not None
    assert isinstance(saved_user.created_at, datetime)


def test_user_unique_email(db_session):
    """Test that user emails must be unique."""
    role = Role(id=1, name="user")
    db_session.add(role)
    db_session.commit()

    user1 = User(
        id=1,
        email="test@example.com",
        oauth_provider="google",
        oauth_sub="12345",
        name="User 1",
        id_role=1,
    )
    user2 = User(
        id=2,
        email="test@example.com",
        oauth_provider="google",
        oauth_sub="67890",
        name="User 2",
        id_role=1,
    )

    db_session.add(user1)
    db_session.commit()

    db_session.add(user2)
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_user_optional_photo(db_session):
    """Test that photo field is optional."""
    role = Role(id=1, name="user")
    db_session.add(role)
    db_session.commit()

    user = User(
        id=1,
        email="test@example.com",
        oauth_provider="google",
        oauth_sub="12345",
        name="Test User",
        id_role=1,
    )
    db_session.add(user)
    db_session.commit()

    saved_user = db_session.query(User).filter_by(id=1).first()
    assert saved_user.photo is None


def test_create_staff_whitelist(db_session):
    """Test creating a StaffWhitelist model instance."""
    role = Role(id=1, name="staff")
    db_session.add(role)
    db_session.commit()

    staff = StaffWhitelist(id=1, email="staff@example.com", id_role=1)
    db_session.add(staff)
    db_session.commit()

    saved_staff = db_session.query(StaffWhitelist).filter_by(id=1).first()
    assert saved_staff is not None
    assert saved_staff.email == "staff@example.com"
    assert saved_staff.id_role == 1


def test_staff_whitelist_unique_email(db_session):
    """Test that staff whitelist emails must be unique."""
    role = Role(id=1, name="staff")
    db_session.add(role)
    db_session.commit()

    staff1 = StaffWhitelist(id=1, email="staff@example.com", id_role=1)
    staff2 = StaffWhitelist(id=2, email="staff@example.com", id_role=1)

    db_session.add(staff1)
    db_session.commit()

    db_session.add(staff2)
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_create_user_session(db_session):
    """Test creating a UserSession model instance."""
    # Create role and user
    role = Role(id=1, name="user")
    db_session.add(role)
    db_session.commit()

    user = User(
        id=1,
        email="test@example.com",
        oauth_provider="google",
        oauth_sub="12345",
        name="Test User",
        id_role=1,
    )
    db_session.add(user)
    db_session.commit()

    # Create session
    session = UserSession(
        id=1, id_user=1, token_version=1, push_token="test-push-token"
    )
    db_session.add(session)
    db_session.commit()

    saved_session = db_session.query(UserSession).filter_by(id=1).first()
    assert saved_session is not None
    assert saved_session.id_user == 1
    assert saved_session.token_version == 1
    assert saved_session.push_token == "test-push-token"
    assert saved_session.created_at is not None
    assert isinstance(saved_session.created_at, datetime)


def test_user_session_optional_push_token(db_session):
    """Test that push_token field is optional."""
    role = Role(id=1, name="user")
    db_session.add(role)
    db_session.commit()

    user = User(
        id=1,
        email="test@example.com",
        oauth_provider="google",
        oauth_sub="12345",
        name="Test User",
        id_role=1,
    )
    db_session.add(user)
    db_session.commit()

    session = UserSession(id=1, id_user=1, token_version=1)
    db_session.add(session)
    db_session.commit()

    saved_session = db_session.query(UserSession).filter_by(id=1).first()
    assert saved_session.push_token is None


def test_user_session_default_token_version(db_session):
    """Test that token_version has default value of 1."""
    role = Role(id=1, name="user")
    db_session.add(role)
    db_session.commit()

    user = User(
        id=1,
        email="test@example.com",
        oauth_provider="google",
        oauth_sub="12345",
        name="Test User",
        id_role=1,
    )
    db_session.add(user)
    db_session.commit()

    session = UserSession(id=1, id_user=1)
    db_session.add(session)
    db_session.commit()

    saved_session = db_session.query(UserSession).filter_by(id=1).first()
    assert saved_session.token_version == 1


def test_foreign_key_relationships(db_session):
    """Test that foreign key relationships work correctly."""
    # Create role
    role = Role(id=1, name="admin")
    db_session.add(role)
    db_session.commit()

    # Create user
    user = User(
        id=1,
        email="admin@example.com",
        oauth_provider="google",
        oauth_sub="12345",
        name="Admin User",
        id_role=1,
    )
    db_session.add(user)
    db_session.commit()

    # Create session
    session = UserSession(id=1, id_user=1, token_version=1)
    db_session.add(session)
    db_session.commit()

    # Create staff whitelist
    staff = StaffWhitelist(id=1, email="staff@example.com", id_role=1)
    db_session.add(staff)
    db_session.commit()

    # Verify all relationships
    saved_user = db_session.query(User).filter_by(id=1).first()
    saved_session = db_session.query(UserSession).filter_by(id=1).first()
    saved_staff = db_session.query(StaffWhitelist).filter_by(id=1).first()

    assert saved_user.id_role == role.id
    assert saved_session.id_user == user.id
    assert saved_staff.id_role == role.id
