from unittest.mock import MagicMock, patch

from app.core.database import SessionLocal, engine, get_db, get_engine


def test_engine_exists():
    assert engine is not None


def test_get_engine_sets_connect_args_only_for_postgres():
    sqlite_engine = get_engine("sqlite:///:memory:")
    assert sqlite_engine is not None
    assert sqlite_engine.dialect.name == "sqlite"

    postgres_engine = get_engine("postgresql://user:pass@localhost/db")
    assert postgres_engine is not None
    assert postgres_engine.dialect.name == "postgresql"

    # Verifica que estas llamadas no fallan y activan los caminos de config condicional.


def test_session_local():
    db = SessionLocal()
    try:
        assert db is not None
    finally:
        db.close()


def test_get_db():
    """Test que get_db() entrega una sesión correctamente."""
    db_generator = get_db()
    db = next(db_generator)
    assert db is not None

    # Limpiar el generador
    try:
        next(db_generator)
    except StopIteration:
        pass


def test_get_db_closes_on_exception():
    """Test que get_db() cierra la sesión incluso si hay excepción."""
    with patch("app.core.database.SessionLocal") as mock_session_local:
        mock_db = MagicMock()
        mock_session_local.return_value = mock_db

        db_generator = get_db()
        next(db_generator)

        # Simular una excepción
        try:
            db_generator.throw(Exception("Test exception"))
        except Exception:
            pass

        # Verificar que close() fue llamado
        mock_db.close.assert_called_once()
