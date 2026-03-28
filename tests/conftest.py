import os

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")
os.environ.setdefault("SECRET_KEY", "test-secret-key")

from app.core.database import Base  # noqa: E402
from app.main import app  # noqa: E402
from app.models.auth.role import Role  # noqa: E402

TEST_DATABASE_URL = "sqlite:///./test.db"


@pytest.fixture(scope="session")
def test_engine():
    engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def db(test_engine):
    session_factory = sessionmaker(bind=test_engine)
    session = session_factory()
    yield session
    session.rollback()
    session.close()


@pytest.fixture
def clear_dependency_overrides():
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def user_role(db):
    from sqlalchemy import select

    role = db.execute(select(Role).where(Role.name == "user")).scalar_one_or_none()
    if not role:
        role = Role(name="user")
        db.add(role)
        db.commit()
    return role
