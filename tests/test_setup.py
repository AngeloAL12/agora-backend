from app.core.database import get_db
from app.models.auth.role import Role
from app.models.auth.user import User


def insert_role(id=1, name="admin"):
    db = next(get_db())
    role = db.query(Role).filter(Role.name == name).first()
    if not role:
        role = Role(id=id, name=name)
        db.add(role)
        db.commit()
    return role


def insert_user(id=1, email="test@example.com", role_id=1):
    db = next(get_db())
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
    return user
