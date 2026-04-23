import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.redis_service import RedisChatManager


class _DummyTask:
    def __init__(self):
        self.cancel_called = False

    def cancel(self):
        self.cancel_called = True


def _noop_create_task(coro):
    """Evita ejecutar tasks reales en tests unitarios de subscribe."""
    coro.close()
    return _DummyTask()


class _PubSubWithMessages:
    def __init__(self, messages):
        self._messages = messages

    async def listen(self):
        for message in self._messages:
            yield message


class _CancelledPubSub:
    async def listen(self):
        raise asyncio.CancelledError
        yield


class _BrokenPubSub:
    async def listen(self):
        raise RuntimeError("broken listener")
        yield


@pytest.mark.asyncio
async def test_redis_connect_success():
    """Test successful Redis connection."""
    manager = RedisChatManager()

    mock_redis = AsyncMock()
    mock_redis.ping = AsyncMock(return_value=True)
    mock_redis.close = AsyncMock()

    async def mock_from_url(*args, **kwargs):
        return mock_redis

    with patch("app.services.redis_service.redis.from_url", mock_from_url):
        with patch("app.services.redis_service.settings") as mock_settings:
            mock_settings.REDIS_URL = "redis://localhost:6379"
            await manager.connect_redis()

    assert manager.redis_client is not None


@pytest.mark.asyncio
async def test_redis_connect_failure():
    """Test Redis connection failure triggers fail-open mode."""
    manager = RedisChatManager()

    async def mock_from_url(*args, **kwargs):
        raise ConnectionError("Connection refused")

    with patch("app.services.redis_service.redis.from_url", mock_from_url):
        with patch("app.services.redis_service.settings") as mock_settings:
            mock_settings.REDIS_URL = "redis://localhost:6379"
            await manager.connect_redis()

    # Should be None in fail-open mode
    assert manager.redis_client is None


@pytest.mark.asyncio
async def test_redis_disconnect_when_connected():
    """Test disconnecting from Redis."""
    manager = RedisChatManager()

    mock_redis = AsyncMock()
    mock_redis.close = AsyncMock()

    manager.redis_client = mock_redis

    await manager.disconnect_redis()

    assert manager.redis_client is None


@pytest.mark.asyncio
async def test_redis_disconnect_when_not_connected():
    """Test disconnecting when Redis is not connected."""
    manager = RedisChatManager()
    manager.redis_client = None

    # Should not raise error
    await manager.disconnect_redis()

    assert manager.redis_client is None


@pytest.mark.asyncio
async def test_subscribe_with_redis():
    """Test subscribing to a channel when Redis is available."""
    manager = RedisChatManager()

    mock_redis = AsyncMock()
    mock_pubsub = AsyncMock()
    mock_pubsub.subscribe = AsyncMock()
    mock_redis.pubsub = MagicMock(return_value=mock_pubsub)

    manager.redis_client = mock_redis

    callback = AsyncMock()
    with patch("app.services.redis_service.create_task", side_effect=_noop_create_task):
        result = await manager.subscribe(club_id=5, user_id=1, callback=callback)

    # Should return the pubsub object
    assert result is not None
    # Should also track locally
    assert "5:1" in manager._local_connections


@pytest.mark.asyncio
async def test_subscribe_without_redis():
    """Test subscribing without Redis (fail-open mode)."""
    manager = RedisChatManager()
    manager.redis_client = None

    callback = AsyncMock()
    result = await manager.subscribe(club_id=5, user_id=1, callback=callback)

    # Should return None and still track locally
    assert result is None
    assert "5:1" in manager._local_connections


@pytest.mark.asyncio
async def test_subscribe_redis_error():
    """Test subscription error handling."""
    manager = RedisChatManager()

    mock_redis = AsyncMock()
    mock_redis.pubsub = MagicMock(side_effect=Exception("Redis error"))

    manager.redis_client = mock_redis

    callback = AsyncMock()
    result = await manager.subscribe(club_id=5, user_id=1, callback=callback)

    # Should return None and still track locally
    assert result is None
    assert "5:1" in manager._local_connections


@pytest.mark.asyncio
async def test_unsubscribe():
    """Test unsubscribing from a channel."""
    manager = RedisChatManager()

    callback = AsyncMock()
    await manager.subscribe(club_id=5, user_id=1, callback=callback)

    # Verify subscribed
    assert "5:1" in manager._local_connections

    await manager.unsubscribe(club_id=5, user_id=1, callback=callback)

    # Should be removed
    assert "5:1" not in manager._local_connections


@pytest.mark.asyncio
async def test_unsubscribe_keeps_channel_when_still_has_subscribers():
    """Test unsubscribe does not close pubsub when other local subscribers exist."""
    manager = RedisChatManager()

    callback1 = AsyncMock()
    callback2 = AsyncMock()
    pubsub = AsyncMock()
    task = _DummyTask()

    manager._local_connections = {
        "5:1": {callback1},
        "5:2": {callback2},
    }
    manager._pubsubs = {"club:chat:5": pubsub}
    manager._listener_tasks = {"club:chat:5": task}

    await manager.unsubscribe(club_id=5, user_id=1, callback=callback1)

    assert "5:1" not in manager._local_connections
    assert "club:chat:5" in manager._pubsubs
    assert task.cancel_called is False
    pubsub.unsubscribe.assert_not_called()


@pytest.mark.asyncio
async def test_unsubscribe_closes_channel_when_last_subscriber_leaves():
    """Test unsubscribe closes pubsub and cancels task when no subscribers remain."""
    manager = RedisChatManager()

    callback = AsyncMock()
    pubsub = AsyncMock()
    pubsub.unsubscribe = AsyncMock()
    pubsub.close = AsyncMock()
    task = _DummyTask()

    manager._local_connections = {"5:1": {callback}}
    manager._pubsubs = {"club:chat:5": pubsub}
    manager._listener_tasks = {"club:chat:5": task}

    await manager.unsubscribe(club_id=5, user_id=1, callback=callback)

    assert "club:chat:5" not in manager._pubsubs
    assert "club:chat:5" not in manager._listener_tasks
    assert task.cancel_called is True
    pubsub.unsubscribe.assert_awaited_once_with("club:chat:5")
    pubsub.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_publish_with_redis():
    """Test publishing a message with Redis."""
    manager = RedisChatManager()

    mock_redis = AsyncMock()
    mock_redis.publish = AsyncMock()

    manager.redis_client = mock_redis

    manager._broadcast_local = AsyncMock()

    message = {"content": "Hola", "id": 1}
    await manager.publish_message(club_id=5, message=message)

    # Should have called publish
    assert mock_redis.publish.called
    call_args = mock_redis.publish.call_args
    assert call_args[0][0] == "club:chat:5"
    manager._broadcast_local.assert_not_called()


@pytest.mark.asyncio
async def test_publish_without_redis():
    """Test publishing without Redis (fail-open mode)."""
    manager = RedisChatManager()
    manager.redis_client = None

    message = {"content": "Hola", "id": 1}
    # Should not raise error
    await manager.publish_message(club_id=5, message=message)


@pytest.mark.asyncio
async def test_publish_redis_error(monkeypatch):
    """Test publish error handling."""
    manager = RedisChatManager()

    mock_redis = AsyncMock()
    mock_redis.publish = AsyncMock(side_effect=Exception("Redis publish failed"))

    manager.redis_client = mock_redis

    manager._broadcast_local = AsyncMock()

    message = {"content": "Hola", "id": 1}
    # Should not raise error, fallback to local
    await manager.publish_message(club_id=5, message=message)
    manager._broadcast_local.assert_awaited_once_with(5, message)


@pytest.mark.asyncio
async def test_disconnect_redis_cleans_listener_tasks_and_pubsubs():
    """Test disconnect cleans listener tasks and pubsubs before closing redis client."""
    manager = RedisChatManager()

    task = _DummyTask()
    pubsub = AsyncMock()
    pubsub.close = AsyncMock()
    redis_client = AsyncMock()
    redis_client.close = AsyncMock()

    manager._listener_tasks = {"club:chat:5": task}
    manager._pubsubs = {"club:chat:5": pubsub}
    manager.redis_client = redis_client

    await manager.disconnect_redis()

    assert task.cancel_called is True
    assert manager._listener_tasks == {}
    assert manager._pubsubs == {}
    pubsub.close.assert_awaited_once()
    redis_client.close.assert_awaited_once()
    assert manager.redis_client is None


@pytest.mark.asyncio
async def test_broadcast_local():
    """Test broadcasting to local connections."""
    manager = RedisChatManager()

    callback1 = AsyncMock()
    callback2 = AsyncMock()

    # Subscribe two users to club 5
    await manager.subscribe(club_id=5, user_id=1, callback=callback1)
    await manager.subscribe(club_id=5, user_id=2, callback=callback2)

    message = {"content": "Hola", "id": 1}
    await manager._broadcast_local(club_id=5, message=message)

    # Both callbacks should be called
    callback1.assert_called_once_with(message)
    callback2.assert_called_once_with(message)


@pytest.mark.asyncio
async def test_broadcast_local_callback_error():
    """Test broadcast handles callback errors."""
    manager = RedisChatManager()

    callback_ok = AsyncMock()
    callback_error = AsyncMock(side_effect=Exception("Callback failed"))

    await manager.subscribe(club_id=5, user_id=1, callback=callback_ok)
    await manager.subscribe(club_id=5, user_id=2, callback=callback_error)

    message = {"content": "Hola", "id": 1}
    # Should not raise error
    await manager._broadcast_local(club_id=5, message=message)

    # Both should be called
    callback_ok.assert_called_once()
    callback_error.assert_called_once()


@pytest.mark.asyncio
async def test_get_connected_user_ids():
    """Test getting connected user IDs for a club."""
    manager = RedisChatManager()

    callback = AsyncMock()
    await manager.subscribe(club_id=5, user_id=1, callback=callback)
    await manager.subscribe(club_id=5, user_id=2, callback=callback)
    await manager.subscribe(club_id=6, user_id=1, callback=callback)

    connected_ids = await manager.get_connected_user_ids(club_id=5)

    assert connected_ids == {1, 2}


@pytest.mark.asyncio
async def test_get_connected_user_ids_empty():
    """Test getting connected user IDs when no one is connected."""
    manager = RedisChatManager()

    connected_ids = await manager.get_connected_user_ids(club_id=5)

    assert connected_ids == set()


@pytest.mark.asyncio
async def test_channel_key_generation():
    """Test channel key generation."""
    manager = RedisChatManager()

    channel = manager._get_channel_key(club_id=42)

    assert channel == "club:chat:42"


@pytest.mark.asyncio
async def test_user_key_generation():
    """Test user key generation."""
    manager = RedisChatManager()

    user_key = manager._get_user_key(club_id=5, user_id=10)

    assert user_key == "5:10"


@pytest.mark.asyncio
async def test_multiple_callbacks_same_user():
    """Test multiple callbacks for the same user."""
    manager = RedisChatManager()

    callback1 = AsyncMock()
    callback2 = AsyncMock()

    await manager.subscribe(club_id=5, user_id=1, callback=callback1)
    await manager.subscribe(club_id=5, user_id=1, callback=callback2)

    message = {"content": "Hola"}
    await manager._broadcast_local(club_id=5, message=message)

    # Both callbacks should be called
    callback1.assert_called_once()
    callback2.assert_called_once()


@pytest.mark.asyncio
async def test_resubscribe_to_same_channel(monkeypatch):
    """Test resubscribing to the same channel doesn't create duplicate subscriptions."""
    manager = RedisChatManager()

    mock_redis = AsyncMock()
    mock_pubsub = AsyncMock()
    mock_pubsub.subscribe = AsyncMock()
    mock_redis.pubsub = MagicMock(return_value=mock_pubsub)

    manager.redis_client = mock_redis

    callback1 = AsyncMock()
    callback2 = AsyncMock()

    # Subscribe two users to the same club
    with patch("app.services.redis_service.create_task", side_effect=_noop_create_task):
        result1 = await manager.subscribe(club_id=5, user_id=1, callback=callback1)
        result2 = await manager.subscribe(club_id=5, user_id=2, callback=callback2)

    # Both should get the same pubsub object
    assert result1 is result2
    # Subscribe should only be called once
    assert mock_pubsub.subscribe.call_count == 1


@pytest.mark.asyncio
async def test_listen_broadcasts_only_valid_messages():
    """Test Redis listener only rebroadcasts valid message payloads."""
    manager = RedisChatManager()
    manager._broadcast_local = AsyncMock()

    pubsub = _PubSubWithMessages(
        [
            {"type": "subscribe", "data": 1},
            {"type": "message", "data": ""},
            {"type": "message", "data": "{invalid"},
            {"type": "message", "data": '{"content": "Hola"}'},
            {
                "type": "message",
                "data": '{"id_club": 5, "content": "Hola a todos"}',
            },
        ]
    )

    await manager._listen("club:chat:5", pubsub)

    manager._broadcast_local.assert_awaited_once_with(
        5, {"id_club": 5, "content": "Hola a todos"}
    )


@pytest.mark.asyncio
async def test_listen_reraises_cancelled_error():
    """Test listener propagates task cancellation."""
    manager = RedisChatManager()

    with pytest.raises(asyncio.CancelledError):
        await manager._listen("club:chat:5", _CancelledPubSub())


@pytest.mark.asyncio
async def test_listen_handles_unexpected_error_without_crashing():
    """Test listener logs and swallows unexpected errors from pubsub.listen."""
    manager = RedisChatManager()

    # Should not raise
    await manager._listen("club:chat:5", _BrokenPubSub())
