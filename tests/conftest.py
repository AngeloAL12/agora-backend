import os

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")
os.environ.setdefault("SECRET_KEY", "test-secret-key")

from app.core.database import Base  # noqa: E402
from app.main import app  # 👈 AGREGADO

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


# 👇 ESTE ES EL QUE TE FALTABA
@pytest.fixture
def clear_dependency_overrides():
    yield
    app.dependency_overrides.clear()
