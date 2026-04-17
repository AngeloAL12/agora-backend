from unittest.mock import patch

from app.services.push_service import send_push_notification


def test_send_push_notification_posts_to_expo_with_valid_token():
    token = "ExponentPushToken[abc123]"

    with patch("app.services.push_service.httpx.post") as mock_post:
        send_push_notification(
            token=token,
            title="Hola",
            body="Tienes una actualizacion",
            data={"reference_id": 1},
        )

    mock_post.assert_called_once()
    args, kwargs = mock_post.call_args
    assert args[0] == "https://exp.host/--/api/v2/push/send"
    assert kwargs["json"]["to"] == token
    assert kwargs["json"]["title"] == "Hola"
    assert kwargs["json"]["body"] == "Tienes una actualizacion"
    assert kwargs["json"]["data"] == {"reference_id": 1}
    assert kwargs["json"]["sound"] == "default"


def test_send_push_notification_does_not_post_for_invalid_token():
    with patch("app.services.push_service.httpx.post") as mock_post:
        send_push_notification(
            token="not-an-expo-token",
            title="Hola",
            body="Mensaje",
        )

    mock_post.assert_not_called()


def test_send_push_notification_swallows_http_errors():
    with patch("app.services.push_service.httpx.post") as mock_post:
        mock_post.side_effect = RuntimeError("network down")

        send_push_notification(
            token="ExponentPushToken[abc123]",
            title="Hola",
            body="Mensaje",
        )
