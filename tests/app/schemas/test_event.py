from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from app.schemas.club.event import EventCreate, EventUpdate


def test_event_create_accepts_naive_future_date_and_makes_it_aware():
    future_date = datetime.now() + timedelta(days=3)

    event = EventCreate(
        title="Evento futuro",
        description="Descripcion valida",
        date=future_date,
        latitude=32.6,
        longitude=-115.4,
    )

    assert event.date.tzinfo == UTC


def test_event_create_rejects_past_date():
    with pytest.raises(ValidationError) as exc_info:
        EventCreate(
            title="Evento pasado",
            description="Descripcion valida",
            date=datetime.now() - timedelta(days=1),
            latitude=32.6,
            longitude=-115.4,
        )

    assert "La fecha debe ser futura" in str(exc_info.value)


def test_event_update_allows_none_date():
    event = EventUpdate(date=None)

    assert event.date is None


def test_event_update_rejects_past_aware_date():
    with pytest.raises(ValidationError) as exc_info:
        EventUpdate(date=datetime.now(UTC) - timedelta(hours=1))

    assert "La fecha debe ser futura" in str(exc_info.value)
