import json
import logging
from time import monotonic
from typing import Any

from redis import Redis
from redis.exceptions import RedisError

from app.core.config import settings

logger = logging.getLogger(__name__)


class CacheService:
    def __init__(self) -> None:
        self._client: Redis | None = None
        self._retry_after: float = 0.0

    def _mark_unavailable(self) -> None:
        self._client = None
        cooldown = max(
            float(getattr(settings, "REDIS_RETRY_COOLDOWN_SECONDS", 5.0)),
            0.0,
        )
        self._retry_after = monotonic() + cooldown

    def _get_client(self) -> Redis | None:
        if not settings.REDIS_URL:
            return None

        if self._client is None and monotonic() < self._retry_after:
            return None

        if self._client is None:
            self._client = Redis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                socket_connect_timeout=settings.REDIS_TIMEOUT_SECONDS,
                socket_timeout=settings.REDIS_TIMEOUT_SECONDS,
            )

        return self._client

    def get_json_with_status(self, key: str) -> tuple[dict[str, Any] | None, str]:
        client = self._get_client()
        if client is None:
            return None, "bypass"

        try:
            value = client.get(key)
            if value is None:
                return None, "miss"
            decoded = json.loads(value)
            if isinstance(decoded, dict):
                return decoded, "hit"
            return None, "miss"
        except (RedisError, TypeError, ValueError) as exc:
            logger.warning("Redis get failed for key %s: %s", key, exc)
            self._mark_unavailable()
            return None, "error"

    def set_json(self, key: str, value: dict[str, Any], ttl_seconds: int) -> None:
        client = self._get_client()
        if client is None:
            return

        try:
            client.set(key, json.dumps(value), ex=ttl_seconds)
        except (RedisError, TypeError, ValueError) as exc:
            logger.warning("Redis set failed for key %s: %s", key, exc)
            self._mark_unavailable()

    def delete(self, key: str) -> None:
        client = self._get_client()
        if client is None:
            return

        try:
            client.delete(key)
        except RedisError as exc:
            logger.warning("Redis delete failed for key %s: %s", key, exc)
            self._mark_unavailable()


cache_service = CacheService()
