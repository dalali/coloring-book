"""Default AI provider: OpenAI DALL-E 3 (architecture §6.2).

Keys are read server-side only and never logged or returned (NFR3 / R5).
"""
from __future__ import annotations

import base64

from ..config import Settings
from .base import ContentPolicyError, GenerationUnavailable


def _nearest_dalle_size(size: int) -> str:
    """DALL-E 3 supports a fixed set of sizes; pick the closest square-ish one."""
    if size >= 1536:
        return "1792x1024"
    return "1024x1024"


class OpenAIProvider:
    name = "openai"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._api_key = settings.openai_api_key
        self._timeout = settings.generation_timeout_s

    def generate(self, prompt: str, size: int = 1024) -> bytes:
        # Imported lazily so the module loads even if the SDK is absent.
        from openai import OpenAI

        try:
            from openai import APIError, APITimeoutError, RateLimitError
        except Exception:  # pragma: no cover - SDK shape guard
            APIError = APITimeoutError = RateLimitError = Exception  # type: ignore

        client = OpenAI(api_key=self._api_key, timeout=self._timeout)
        try:
            resp = client.images.generate(
                model="dall-e-3",
                prompt=prompt,
                size=_nearest_dalle_size(size),
                n=1,
                response_format="b64_json",
            )
        except RateLimitError as exc:  # type: ignore[misc]
            raise GenerationUnavailable("Rate limited by the image generator.") from exc
        except APITimeoutError as exc:  # type: ignore[misc]
            raise GenerationUnavailable("The image generator timed out.") from exc
        except APIError as exc:  # type: ignore[misc]
            # Content-policy rejections surface as a 400 from the API.
            status = getattr(exc, "status_code", None)
            message = str(getattr(exc, "message", "") or exc).lower()
            if status == 400 and ("content_policy" in message or "safety" in message or "policy" in message):
                raise ContentPolicyError("That prompt was rejected by the image generator.") from exc
            raise GenerationUnavailable("The image generator returned an error.") from exc
        except Exception as exc:  # network / unexpected
            raise GenerationUnavailable("The image generator is unavailable.") from exc

        try:
            b64 = resp.data[0].b64_json
            return base64.b64decode(b64)
        except Exception as exc:  # pragma: no cover - response shape guard
            raise GenerationUnavailable("The image generator returned no image.") from exc
