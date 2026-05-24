"""Optional AI provider: Stability AI (Stable Diffusion) via REST (architecture §6.3).

Selected only when no OpenAI key is set but a Stability key is. Keys are
server-side only and never logged or returned (NFR3 / R5).
"""
from __future__ import annotations

import httpx

from ..config import Settings
from .base import ContentPolicyError, GenerationUnavailable

_ENDPOINT = "https://api.stability.ai/v2beta/stable-image/generate/core"


class StabilityProvider:
    name = "stability"

    def __init__(self, settings: Settings) -> None:
        self._api_key = settings.stability_api_key
        self._timeout = settings.generation_timeout_s

    def generate(self, prompt: str, size: int = 1024) -> bytes:
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Accept": "image/*",
        }
        files = {"prompt": (None, prompt), "output_format": (None, "png")}
        try:
            resp = httpx.post(_ENDPOINT, headers=headers, files=files, timeout=self._timeout)
        except httpx.TimeoutException as exc:
            raise GenerationUnavailable("The image generator timed out.") from exc
        except httpx.HTTPError as exc:
            raise GenerationUnavailable("The image generator is unavailable.") from exc

        if resp.status_code == 200:
            return resp.content
        if resp.status_code in (400, 403):
            raise ContentPolicyError("That prompt was rejected by the image generator.")
        raise GenerationUnavailable("The image generator returned an error.")
