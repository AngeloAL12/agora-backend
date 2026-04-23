from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.redis_service import RedisChatManager


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
async def test_publish_with_redis():
    """Test publishing a message with Redis."""
    manager = RedisChatManager()

    mock_redis = AsyncMock()
    mock_redis.publish = AsyncMock()

    manager.redis_client = mock_redis

    message = {"content": "Hola", "id": 1}
    await manager.publish_message(club_id=5, message=message)

    # Should have called publish
    assert mock_redis.publish.called
    call_args = mock_redis.publish.call_args
    assert call_args[0][0] == "club:chat:5"


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

    message = {"content": "Hola", "id": 1}
    # Should not raise error, fallback to local
    await manager.publish_message(club_id=5, message=message)


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
    result1 = await manager.subscribe(club_id=5, user_id=1, callback=callback1)
    result2 = await manager.subscribe(club_id=5, user_id=2, callback=callback2)

    # Both should get the same pubsub object
    assert result1 is result2
    # Subscribe should only be called once
    assert mock_pubsub.subscribe.call_count == 1
