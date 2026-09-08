import logging

import httpx

EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"

logger = logging.getLogger(__name__)


def _is_valid_expo_token(token: str) -> bool:
    return token.startswith("ExponentPushToken[")


def send_push_notification(
    token: str,
    title: str,
    body: str,
    data: dict | None = None,
) -> None:
    if not _is_valid_expo_token(token):
        logger.warning("Invalid Expo push token format")
        return

    payload = {
        "to": token,
        "title": title,
        "body": body,
        "data": data or {},
        "sound": "default",
    }

    try:
        response = httpx.post(
            EXPO_PUSH_URL,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=10.0,
        )
        response.raise_for_status()
    except Exception:
        logger.exception("Failed to send Expo push notification")
