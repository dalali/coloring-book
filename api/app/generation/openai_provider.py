"""Default AI provider: OpenAI gpt-image-1 (architecture §6.2).

Keys are read server-side only and never logged or returned (NFR3 / R5).
"""
from __future__ import annotations

import base64
import logging

from ..config import Settings
from .base import ContentPolicyError, GenerationUnavailable

logger = logging.getLogger(__name__)


def _nearest_size(size: int) -> str:
    """gpt-image-1 supports 1024x1024, 1536x1024, 1024x1536."""
    if size >= 1536:
        return "1536x1024"
    return "1024x1024"


class OpenAIProvider:
    name = "openai"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._api_key = settings.openai_api_key
        self._timeout = settings.generation_timeout_s

    def generate(self, prompt: str, size: int = 1024) -> bytes:
        from openai import OpenAI

        try:
            from openai import APIError, APITimeoutError, RateLimitError
        except Exception:  # pragma: no cover
            APIError = APITimeoutError = RateLimitError = Exception  # type: ignore

        client = OpenAI(api_key=self._api_key, timeout=self._timeout)
        try:
            resp = client.images.generate(
                model="gpt-image-1",
                prompt=prompt,
                size=_nearest_size(size),
                n=1,
            )
        except RateLimitError as exc:  # type: ignore[misc]
            raise GenerationUnavailable("Rate limited by the image generator.") from exc
        except APITimeoutError as exc:  # type: ignore[misc]
            raise GenerationUnavailable("The image generator timed out.") from exc
        except APIError as exc:  # type: ignore[misc]
            status = getattr(exc, "status_code", None)
            message = str(getattr(exc, "message", "") or exc).lower()
            logger.error("OpenAI APIError status=%s: %s", status, exc)
            if status == 400 and any(w in message for w in ("content_policy", "safety", "policy")):
                raise ContentPolicyError("That prompt was rejected by the image generator.") from exc
            if status == 401:
                raise GenerationUnavailable("OpenAI API key is invalid or expired.") from exc
            if status == 429:
                raise GenerationUnavailable("OpenAI quota exceeded — check usage at platform.openai.com.") from exc
            raise GenerationUnavailable(f"OpenAI error ({status}): {str(exc)[:200]}") from exc
        except Exception as exc:
            logger.error("OpenAI unexpected error: %s", exc)
            raise GenerationUnavailable(f"Image generator unavailable: {type(exc).__name__}") from exc

        try:
            b64 = resp.data[0].b64_json
            return base64.b64decode(b64)
        except Exception as exc:
            logger.error("Failed to decode generated image: %s", exc)
            raise GenerationUnavailable("The image generator returned no image.") from exc
