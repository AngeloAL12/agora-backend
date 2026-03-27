import os
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.database import Base, get_db
from app.main import app

# Forzar SQLite en entorno de pruebas
os.environ["DATABASE_URL"] = "sqlite:///./test.db"
os.environ.setdefault("SECRET_KEY", "test-secret-key")

TEST_DATABASE_URL = os.environ["DATABASE_URL"]

engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})

TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="session", autouse=True)
def create_test_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db():
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


def override_get_db():
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(autouse=True)
def apply_override():
    app.dependency_overrides[get_db] = override_get_db
