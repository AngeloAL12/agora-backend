from app.core.config import Settings


def test_settings_loaded(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://test")
    monkeypatch.setenv("SECRET_KEY", "test")

    settings = Settings()

    assert settings.DATABASE_URL == "postgresql://test"
    assert settings.SECRET_KEY == "test"
