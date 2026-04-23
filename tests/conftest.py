import os

import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.main import app
from app.models.auth.role import Role

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///:memory:")
SECRET_KEY = os.getenv("SECRET_KEY", "test-secret-key")

if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):
        del connection_record
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
else:
    engine = create_engine(DATABASE_URL)

TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="session", autouse=True)
def create_test_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def apply_override():
    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def db():
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(autouse=True)
def clean_db(db):
    if DATABASE_URL.startswith("sqlite"):
        for table in reversed(Base.metadata.sorted_tables):
            db.execute(table.delete())
        db.commit()
    else:
        table_names = ", ".join(
            f'"{t.name}"' for t in reversed(Base.metadata.sorted_tables)
        )
        db.execute(text(f"TRUNCATE {table_names} RESTART IDENTITY CASCADE"))
        db.commit()
    yield


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
