import re
import unicodedata

from fastapi import HTTPException, status

from app.core.config import settings


def _normalize(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    without_accents = "".join(
        char for char in decomposed if not unicodedata.combining(char)
    )
    return re.sub(r"\s+", " ", without_accents).strip()


def _blocked_terms() -> tuple[str, ...]:
    return tuple(
        normalized
        for term in settings.CONTENT_MODERATION_BLOCKED_TERMS.split(",")
        if (normalized := _normalize(term))
    )


def is_content_allowed(content: str) -> bool:
    normalized = _normalize(content)
    return not any(term in normalized for term in _blocked_terms())


def ensure_content_allowed(content: str) -> None:
    if not is_content_allowed(content):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Este contenido podría infringir las normas de la comunidad.",
        )
