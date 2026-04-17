import pytest

import app.core.database as db_module
import app.routers.complaints as complaints_module
from tests.conftest import TestingSessionLocal


@pytest.fixture(autouse=True)
def patch_session_local():
    original = db_module.SessionLocal
    db_module.SessionLocal = TestingSessionLocal
    yield
    db_module.SessionLocal = original


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
