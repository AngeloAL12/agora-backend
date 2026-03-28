from app.models.auth.role import Role
from app.models.auth.user import User
from tests.conftest import TestingSessionLocal


def insert_role(id=1, name="admin"):
    db = TestingSessionLocal()
    role = db.query(Role).filter(Role.name == name).first()
    if not role:
        role = Role(id=id, name=name)
        db.add(role)
        db.commit()
    db.close()
    return role


def insert_user(id=1, email="test@example.com", role_id=1):
    db = TestingSessionLocal()
    user = db.query(User).filter(User.id == id).first()
    if not user:
        user = User(
            id=id,
            email=email,
            oauth_provider="test",
            oauth_sub="sub",
            name="Test User",
            photo=None,
            id_role=role_id,
            is_active=True,
        )
        db.add(user)
        db.commit()
    db.close()
    return user
