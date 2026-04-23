import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_settings_loaded(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://test")
    monkeypatch.setenv("SECRET_KEY", "test")
    monkeypatch.setenv("R2_ACCOUNT_ID", "abc123")
    monkeypatch.setenv("R2_ACCESS_KEY_ID", "key-id")
    monkeypatch.setenv("R2_SECRET_ACCESS_KEY", "secret")
    monkeypatch.setenv("R2_BUCKET_PRIVATE", "priv-bucket")
    monkeypatch.setenv("R2_BUCKET_PUBLIC", "pub-bucket")
    monkeypatch.delenv("REDIS_URL", raising=False)

    settings = Settings(_env_file=None)

    assert settings.DATABASE_URL == "postgresql://test"
    assert settings.SECRET_KEY == "test"
    assert settings.REDIS_URL == "redis://localhost:6379/0"


def test_r2_endpoint_derived_from_account_id(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://test")
    monkeypatch.setenv("SECRET_KEY", "test")
    monkeypatch.setenv("R2_ACCOUNT_ID", "my-account-123")
    monkeypatch.setenv("R2_ACCESS_KEY_ID", "key-id")
    monkeypatch.setenv("R2_SECRET_ACCESS_KEY", "secret")
    monkeypatch.setenv("R2_BUCKET_PRIVATE", "priv-bucket")
    monkeypatch.setenv("R2_BUCKET_PUBLIC", "pub-bucket")

    settings = Settings()

    assert settings.R2_ENDPOINT == "https://my-account-123.r2.cloudflarestorage.com"


def test_r2_endpoint_can_be_overridden(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://test")
    monkeypatch.setenv("SECRET_KEY", "test")
    monkeypatch.setenv("R2_ACCOUNT_ID", "my-account-123")
    monkeypatch.setenv("R2_ACCESS_KEY_ID", "key-id")
    monkeypatch.setenv("R2_SECRET_ACCESS_KEY", "secret")
    monkeypatch.setenv("R2_BUCKET_PRIVATE", "priv-bucket")
    monkeypatch.setenv("R2_BUCKET_PUBLIC", "pub-bucket")
    monkeypatch.setenv("R2_ENDPOINT", "https://custom-endpoint.example.com")

    settings = Settings()

    assert settings.R2_ENDPOINT == "https://custom-endpoint.example.com"


@pytest.mark.parametrize(
    "missing_var",
    [
        "R2_ACCOUNT_ID",
        "R2_ACCESS_KEY_ID",
        "R2_SECRET_ACCESS_KEY",
        "R2_BUCKET_PRIVATE",
        "R2_BUCKET_PUBLIC",
    ],
)
def test_missing_r2_var_raises(monkeypatch, missing_var):
    base_vars = {
        "DATABASE_URL": "postgresql://test",
        "SECRET_KEY": "test",
        "R2_ACCOUNT_ID": "account",
        "R2_ACCESS_KEY_ID": "key-id",
        "R2_SECRET_ACCESS_KEY": "secret",
        "R2_BUCKET_PRIVATE": "priv",
        "R2_BUCKET_PUBLIC": "pub",
    }
    for key, value in base_vars.items():
        monkeypatch.setenv(key, value)
    monkeypatch.delenv(missing_var)

    with pytest.raises(ValidationError):
        # _env_file=None prevents reading the real .env file, so only
        # environment variables set above are considered.
        Settings(_env_file=None)
