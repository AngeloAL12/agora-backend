import pytest

import app.core.database as db_module
import app.routers.complaints as complaints_module
from app.services.redis_service import redis_chat_manager
from tests.conftest import TestingSessionLocal


@pytest.fixture(autouse=True)
def patch_session_local():
    original = db_module.SessionLocal
    db_module.SessionLocal = TestingSessionLocal
    yield
    db_module.SessionLocal = original


@pytest.fixture(autouse=True)
def reset_redis_chat_manager():
    """Clear global redis_chat_manager state between tests.

    The manager holds _local_connections and _listener_tasks as module-level
    state. Stale entries from a previous WebSocket test can leak into the next
    test and keep background asyncio Tasks alive, which in turn hold open DB
    connections and prevent PostgreSQL DELETE/TRUNCATE from acquiring locks.
    """
    redis_chat_manager._local_connections.clear()
    redis_chat_manager._pubsubs.clear()
    for task in redis_chat_manager._listener_tasks.values():
        task.cancel()
    redis_chat_manager._listener_tasks.clear()
    yield
    redis_chat_manager._local_connections.clear()
    redis_chat_manager._pubsubs.clear()
    for task in redis_chat_manager._listener_tasks.values():
        task.cancel()
    redis_chat_manager._listener_tasks.clear()


@pytest.fixture(autouse=True)
def patch_notification_tasks(monkeypatch):
    """
    Replace background notification helpers with no-ops by default.
    Tests that need to assert on notifications should monkeypatch
    these themselves (the last monkeypatch wins).
    """
    monkeypatch.setattr(
        complaints_module,
        "_notify_complaint_submitted",
        lambda *a, **kw: None,
    )
    monkeypatch.setattr(
        complaints_module,
        "_notify_complaint_status_changed",
        lambda *a, **kw: None,
    )
