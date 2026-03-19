from app.core.database import SessionLocal, engine


def test_engine_exists():
    assert engine is not None


def test_session_local():
    db = SessionLocal()
    try:
        assert db is not None
    finally:
        db.close()
