import asyncio
import json
import logging
from asyncio import CancelledError, Task, create_task
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
        self._listener_tasks: dict[str, Task] = {}

    async def connect_redis(self) -> None:
        """Conecta al servidor Redis."""
        if not settings.REDIS_URL:
            logger.info("REDIS_URL no configurado; usando solo conexiones locales")
            return
        try:
            redis_kwargs = {
                "encoding": "utf-8",
                "decode_responses": True,
                "socket_connect_timeout": settings.REDIS_SOCKET_CONNECT_TIMEOUT,
                "health_check_interval": settings.REDIS_HEALTH_CHECK_INTERVAL,
            }

            if settings.REDIS_SOCKET_TIMEOUT is not None:
                redis_kwargs["socket_timeout"] = settings.REDIS_SOCKET_TIMEOUT

            self.redis_client = await redis.from_url(
                settings.REDIS_URL,
                **redis_kwargs,
            )
            await self.redis_client.ping()
            logger.info("Conectado a Redis exitosamente")
        except Exception as e:
            logger.error(f"Error conectando a Redis: {e}")
            logger.info("Iniciando modo fail-open: usando solo conexiones locales")
            self.redis_client = None

    async def disconnect_redis(self) -> None:
        """Desconecta del servidor Redis."""
        tasks = list(self._listener_tasks.values())
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

        self._listener_tasks.clear()

        for pubsub in self._pubsubs.values():
            try:
                await asyncio.wait_for(pubsub.close(), timeout=2.0)
            except (TimeoutError, Exception) as e:
                logger.debug(f"pubsub.close() ignorado: {e}")

        self._pubsubs.clear()

        if self.redis_client:
            try:
                await asyncio.wait_for(self.redis_client.close(), timeout=2.0)
            except (TimeoutError, Exception) as e:
                logger.debug(f"redis_client.close() ignorado: {e}")
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
                self._listener_tasks[channel] = create_task(
                    self._listen(channel, pubsub)
                )

            return self._pubsubs[channel]
        except Exception as e:
            logger.error(f"Error suscribiéndose a Redis: {e}")
            return None

    async def unsubscribe(self, club_id: int, user_id: int, callback: Callable) -> None:
        """Desuscribe del canal de un club."""
        user_key = self._get_user_key(club_id, user_id)
        channel = self._get_channel_key(club_id)

        if user_key in self._local_connections:
            self._local_connections[user_key].discard(callback)
            if not self._local_connections[user_key]:
                del self._local_connections[user_key]

        has_local_subscribers = any(
            local_key.startswith(f"{club_id}:")
            for local_key in self._local_connections.keys()
        )

        if has_local_subscribers:
            return

        if task := self._listener_tasks.pop(channel, None):
            task.cancel()

        if pubsub := self._pubsubs.pop(channel, None):
            await pubsub.unsubscribe(channel)
            await pubsub.close()

    async def publish_message(self, club_id: int, message: dict) -> None:
        """
        Publica un mensaje a través de Redis Pub/Sub.

        Args:
            club_id: ID del club
            message: Diccionario con los datos del mensaje
        """
        channel = self._get_channel_key(club_id)

        # Publicar a Redis si está disponible
        if self.redis_client:
            try:
                message_json = json.dumps(message)
                await self.redis_client.publish(channel, message_json)
                return
            except Exception as e:
                logger.error(f"Error publicando a Redis: {e}")
                logger.info("Fallback a broadcast local")

        # Sempre hacer broadcast local
        await self._broadcast_local(club_id, message)

    async def _listen(self, channel: str, pubsub: PubSub) -> None:
        """Escucha mensajes Redis de un canal y los rebroadcast localmente."""
        backoff = 1.0
        while True:
            try:
                async for message in pubsub.listen():
                    if message.get("type") != "message":
                        continue

                    payload = message.get("data")
                    if not payload:
                        continue

                    try:
                        decoded = json.loads(payload)
                    except json.JSONDecodeError:
                        logger.error("Mensaje Redis inválido en canal %s", channel)
                        continue

                    # channel format: "club:chat:{club_id}"
                    club_id = int(channel.split(":")[-1])
                    await self._broadcast_local(club_id, decoded)
            except CancelledError:
                logger.debug("Listener Redis cancelado para canal %s", channel)
                raise
            except Exception as e:
                logger.error(
                    "Error escuchando canal Redis %s (reintentando en %.0fs): %s",
                    channel,
                    backoff,
                    e,
                )
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 60.0)

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
        """Obtiene los IDs de usuarios conectados a un club (solo locales).

        NOTA: Solo rastrea conexiones del proceso actual. En despliegues
        multi-worker (uvicorn --workers N) o multi-pod, usuarios conectados
        a otro worker aparecen como offline y recibirán notificaciones push
        duplicadas. Para eliminar este comportamiento, migrar el tracking a
        Redis (SADD/SREM/SMEMBERS sobre club:{id}:online).
        """
        user_ids = set()
        prefix = f"{club_id}:"

        for user_key in self._local_connections.keys():
            if user_key.startswith(prefix):
                user_id = int(user_key.split(":")[1])
                user_ids.add(user_id)

        return user_ids


# Instancia global del manager
redis_chat_manager = RedisChatManager()
