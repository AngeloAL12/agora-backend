import json
from unittest.mock import MagicMock, patch

from redis.exceptions import RedisError

from app.services.cache_service import CacheService

# ---------------------------------------------------------------------------
# _get_client
# ---------------------------------------------------------------------------


def test_get_client_returns_none_when_no_redis_url(monkeypatch):
    monkeypatch.setattr(
        "app.services.cache_service.settings", MagicMock(REDIS_URL=None)
    )
    svc = CacheService()
    assert svc._get_client() is None


def test_get_client_creates_client_on_first_call(monkeypatch):
    mock_settings = MagicMock(
        REDIS_URL="redis://localhost:6379", REDIS_TIMEOUT_SECONDS=5
    )
    monkeypatch.setattr("app.services.cache_service.settings", mock_settings)

    fake_client = MagicMock()
    with patch("app.services.cache_service.Redis") as mock_redis_cls:
        mock_redis_cls.from_url.return_value = fake_client
        svc = CacheService()
        client = svc._get_client()

    assert client is fake_client
    mock_redis_cls.from_url.assert_called_once()


def test_get_client_reuses_existing_client(monkeypatch):
    mock_settings = MagicMock(
        REDIS_URL="redis://localhost:6379", REDIS_TIMEOUT_SECONDS=5
    )
    monkeypatch.setattr("app.services.cache_service.settings", mock_settings)

    fake_client = MagicMock()
    with patch("app.services.cache_service.Redis") as mock_redis_cls:
        mock_redis_cls.from_url.return_value = fake_client
        svc = CacheService()
        svc._get_client()
        svc._get_client()  # second call must not call from_url again

    mock_redis_cls.from_url.assert_called_once()


# ---------------------------------------------------------------------------
# get_json_with_status
# ---------------------------------------------------------------------------


def test_get_json_returns_bypass_when_no_redis_url(monkeypatch):
    monkeypatch.setattr(
        "app.services.cache_service.settings", MagicMock(REDIS_URL=None)
    )
    svc = CacheService()
    result, status = svc.get_json_with_status("key")
    assert result is None
    assert status == "bypass"


def _svc_with_client(monkeypatch, client):
    """Return a CacheService whose _get_client returns the supplied mock."""
    mock_settings = MagicMock(
        REDIS_URL="redis://localhost:6379", REDIS_TIMEOUT_SECONDS=5
    )
    monkeypatch.setattr("app.services.cache_service.settings", mock_settings)
    with patch("app.services.cache_service.Redis") as mock_redis_cls:
        mock_redis_cls.from_url.return_value = client
        svc = CacheService()
        svc._get_client()  # populate _client
    return svc


def test_get_json_returns_hit_for_existing_dict(monkeypatch):
    client = MagicMock()
    client.get.return_value = json.dumps({"foo": "bar"})

    svc = _svc_with_client(monkeypatch, client)
    result, status = svc.get_json_with_status("key")

    assert status == "hit"
    assert result == {"foo": "bar"}


def test_get_json_returns_miss_when_key_absent(monkeypatch):
    client = MagicMock()
    client.get.return_value = None

    svc = _svc_with_client(monkeypatch, client)
    result, status = svc.get_json_with_status("key")

    assert status == "miss"
    assert result is None


def test_get_json_returns_miss_when_value_is_not_dict(monkeypatch):
    client = MagicMock()
    client.get.return_value = json.dumps([1, 2, 3])

    svc = _svc_with_client(monkeypatch, client)
    result, status = svc.get_json_with_status("key")

    assert status == "miss"
    assert result is None


def test_get_json_returns_error_on_redis_error(monkeypatch):
    client = MagicMock()
    client.get.side_effect = RedisError("boom")

    svc = _svc_with_client(monkeypatch, client)
    result, status = svc.get_json_with_status("key")

    assert status == "error"
    assert result is None
    assert svc._client is None  # client reset


def test_get_json_bypasses_during_retry_cooldown(monkeypatch):
    client = MagicMock()
    client.get.side_effect = RedisError("boom")

    mock_settings = MagicMock(
        REDIS_URL="redis://localhost:6379",
        REDIS_TIMEOUT_SECONDS=5,
        REDIS_RETRY_COOLDOWN_SECONDS=10,
    )
    monkeypatch.setattr("app.services.cache_service.settings", mock_settings)

    with patch("app.services.cache_service.Redis") as mock_redis_cls:
        mock_redis_cls.from_url.return_value = client
        svc = CacheService()

        with patch("app.services.cache_service.monotonic", return_value=100.0):
            first_value, first_status = svc.get_json_with_status("key")
            second_value, second_status = svc.get_json_with_status("key")

    assert first_status == "error"
    assert first_value is None
    assert second_status == "bypass"
    assert second_value is None
    # No reconnect attempt inside cooldown window.
    mock_redis_cls.from_url.assert_called_once()


def test_get_json_returns_error_on_invalid_json(monkeypatch):
    client = MagicMock()
    client.get.return_value = "{invalid"

    svc = _svc_with_client(monkeypatch, client)
    result, status = svc.get_json_with_status("key")

    assert status == "error"
    assert result is None


# ---------------------------------------------------------------------------
# set_json
# ---------------------------------------------------------------------------


def test_set_json_does_nothing_when_no_redis_url(monkeypatch):
    monkeypatch.setattr(
        "app.services.cache_service.settings", MagicMock(REDIS_URL=None)
    )
    svc = CacheService()
    # Must not raise
    svc.set_json("key", {"a": 1}, ttl_seconds=60)


def test_set_json_calls_redis_set(monkeypatch):
    client = MagicMock()
    svc = _svc_with_client(monkeypatch, client)

    svc.set_json("key", {"a": 1}, ttl_seconds=60)

    client.set.assert_called_once_with("key", json.dumps({"a": 1}), ex=60)


def test_set_json_resets_client_on_error(monkeypatch):
    client = MagicMock()
    client.set.side_effect = RedisError("write fail")

    svc = _svc_with_client(monkeypatch, client)
    svc.set_json("key", {"a": 1}, ttl_seconds=60)

    assert svc._client is None


def test_set_json_bypasses_during_retry_cooldown(monkeypatch):
    mock_settings = MagicMock(
        REDIS_URL="redis://localhost:6379",
        REDIS_TIMEOUT_SECONDS=5,
        REDIS_RETRY_COOLDOWN_SECONDS=10,
    )
    monkeypatch.setattr("app.services.cache_service.settings", mock_settings)

    client = MagicMock()
    client.set.side_effect = RedisError("write fail")

    with patch("app.services.cache_service.Redis") as mock_redis_cls:
        mock_redis_cls.from_url.return_value = client
        svc = CacheService()

        with patch("app.services.cache_service.monotonic", return_value=100.0):
            svc.set_json("key", {"a": 1}, ttl_seconds=60)
            svc.set_json("key", {"a": 2}, ttl_seconds=60)

    # First call fails; second call should bypass and not call set again.
    assert client.set.call_count == 1
    mock_redis_cls.from_url.assert_called_once()


# ---------------------------------------------------------------------------
# delete
# ---------------------------------------------------------------------------


def test_delete_does_nothing_when_no_redis_url(monkeypatch):
    monkeypatch.setattr(
        "app.services.cache_service.settings", MagicMock(REDIS_URL=None)
    )
    svc = CacheService()
    # Must not raise
    svc.delete("key")


def test_delete_calls_redis_delete(monkeypatch):
    client = MagicMock()
    svc = _svc_with_client(monkeypatch, client)

    svc.delete("key")

    client.delete.assert_called_once_with("key")


def test_delete_resets_client_on_error(monkeypatch):
    client = MagicMock()
    client.delete.side_effect = RedisError("delete fail")

    svc = _svc_with_client(monkeypatch, client)
    svc.delete("key")

    assert svc._client is None


def test_delete_bypasses_during_retry_cooldown(monkeypatch):
    mock_settings = MagicMock(
        REDIS_URL="redis://localhost:6379",
        REDIS_TIMEOUT_SECONDS=5,
        REDIS_RETRY_COOLDOWN_SECONDS=10,
    )
    monkeypatch.setattr("app.services.cache_service.settings", mock_settings)

    client = MagicMock()
    client.delete.side_effect = RedisError("delete fail")

    with patch("app.services.cache_service.Redis") as mock_redis_cls:
        mock_redis_cls.from_url.return_value = client
        svc = CacheService()

        with patch("app.services.cache_service.monotonic", return_value=100.0):
            svc.delete("key")
            svc.delete("key")

    # First call fails; second call should bypass and not call delete again.
    assert client.delete.call_count == 1
    mock_redis_cls.from_url.assert_called_once()
