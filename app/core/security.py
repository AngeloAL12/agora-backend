from datetime import UTC, datetime, timedelta

from jose import jwt

from app.core.config import settings


def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    # Usamos timezone.utc para compatibilidad
    now = datetime.now(UTC)

    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(
        to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM
    )
    return encoded_jwt
