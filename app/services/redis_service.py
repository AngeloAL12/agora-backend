import json
import logging
from collections.abc import Callable

import redis.asyncio as redis
from redis.asyncio.client import PubSub

from app.core.config import settings

logger = logging.getLogger(__name__)


class RedisChatManager:
    """Maneja conexiones WebSocket y mensajes usando Redis Pub/Sub.

    Permite comunicación entre múltiples instancias de la API a través de Redis.
    """

    def __init__(self):
        self.redis_client: redis.Redis | None = None
        self._local_connections: dict[str, set] = {}
        self._pubsubs: dict[str, PubSub] = {}

    async def connect_redis(self) -> None:
        """Conecta al servidor Redis."""
        try:
            self.redis_client = await redis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True,
            )
            await self.redis_client.ping()
            logger.info("Conectado a Redis exitosamente")
        except Exception as e:
            logger.error(f"Error conectando a Redis: {e}")
            logger.info("Iniciando modo fail-open: usando solo conexiones locales")
            self.redis_client = None

    async def disconnect_redis(self) -> None:
        """Desconecta del servidor Redis."""
        if self.redis_client:
            await self.redis_client.close()
            self.redis_client = None
            logger.info("Desconectado de Redis")

    def _get_channel_key(self, club_id: int) -> str:
        """Genera la clave de canal Redis para un club."""
        return f"club:chat:{club_id}"

    def _get_user_key(self, club_id: int, user_id: int) -> str:
        """Genera la clave local para track de conexiones de usuario."""
        return f"{club_id}:{user_id}"

    async def subscribe(
        self, club_id: int, user_id: int, callback: Callable
    ) -> PubSub | None:
        """
        Se suscribe a mensajes de un club.

        Args:
            club_id: ID del club
            user_id: ID del usuario
            callback: Función async a llamar cuando se reciba un mensaje

        Returns:
            El objeto PubSub si Redis está disponible, None si está en fail-open
        """
        user_key = self._get_user_key(club_id, user_id)

        # Trackear conexión local
        if user_key not in self._local_connections:
            self._local_connections[user_key] = set()
        self._local_connections[user_key].add(callback)

        # Si Redis no está disponible, usar solo conexiones locales
        if not self.redis_client:
            return None

        try:
            channel = self._get_channel_key(club_id)

            # Evitar múltiples suscripciones al mismo canal
            if channel not in self._pubsubs:
                pubsub = self.redis_client.pubsub()
                await pubsub.subscribe(channel)
                self._pubsubs[channel] = pubsub

            return self._pubsubs[channel]
        except Exception as e:
            logger.error(f"Error suscribiéndose a Redis: {e}")
            return None

    async def unsubscribe(self, club_id: int, user_id: int, callback: Callable) -> None:
        """Desuscribe del canal de un club."""
        user_key = self._get_user_key(club_id, user_id)

        if user_key in self._local_connections:
            self._local_connections[user_key].discard(callback)
            if not self._local_connections[user_key]:
                del self._local_connections[user_key]

    async def publish_message(self, club_id: int, message: dict) -> None:
        """
        Publica un mensaje a través de Redis Pub/Sub.

        Args:
            club_id: ID del club
            message: Diccionario con los datos del mensaje
        """
        channel = self._get_channel_key(club_id)
        message_json = json.dumps(message)

        # Publicar a Redis si está disponible
        if self.redis_client:
            try:
                await self.redis_client.publish(channel, message_json)
            except Exception as e:
                logger.error(f"Error publicando a Redis: {e}")
                logger.info("Fallback a broadcast local")

        # Sempre hacer broadcast local
        await self._broadcast_local(club_id, message)

    async def _broadcast_local(self, club_id: int, message: dict) -> None:
        """Hace broadcast a todas las conexiones locales de un club."""
        for user_key, callbacks in list(self._local_connections.items()):
            if user_key.startswith(f"{club_id}:"):
                for callback in callbacks:
                    try:
                        await callback(message)
                    except Exception as e:
                        logger.error(f"Error en callback local: {e}")

    async def get_connected_user_ids(self, club_id: int) -> set[int]:
        """Obtiene los IDs de usuarios conectados a un club (solo locales)."""
        user_ids = set()
        prefix = f"{club_id}:"

        for user_key in self._local_connections.keys():
            if user_key.startswith(prefix):
                user_id = int(user_key.split(":")[1])
                user_ids.add(user_id)

        return user_ids


# Instancia global del manager
redis_chat_manager = RedisChatManager()
