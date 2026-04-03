from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import settings


def get_engine(database_url: str):
    connect_args = {}
    if database_url.startswith("postgres://") or database_url.startswith(
        "postgresql://"
    ):
        connect_args = {"options": "-c client_encoding=UTF8"}

    return create_engine(
        database_url,
        connect_args=connect_args,
    )


engine = get_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
