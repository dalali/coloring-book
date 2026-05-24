"""AI image generation provider abstraction (architecture §6.1, AD3).

The router never imports a concrete provider; it calls ``get_provider`` which
returns ``None`` when no key is configured (text flow disabled, FR11).
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..config import Settings


class GenerationUnavailable(Exception):
    """Provider 5xx / timeout / rate-limit -> mapped to 502 upstream."""


class ContentPolicyError(Exception):
    """Provider rejected the prompt -> mapped to 400 CONTENT_POLICY upstream."""


@runtime_checkable
class ImageProvider(Protocol):
    name: str

    def generate(self, prompt: str, size: int = 1024) -> bytes:
        """Return PNG/JPEG bytes for ``prompt`` or raise a generation error."""
        ...


def get_provider(settings: Settings) -> "ImageProvider | None":
    """Select a provider by configured key (architecture §6.1).

    OpenAI is the default; Stability is the fallback when only its key is set.
    Returns None when no key is configured -> text flow disabled.
    """
    if settings.openai_api_key:
        from .openai_provider import OpenAIProvider

        return OpenAIProvider(settings)
    if settings.stability_api_key:
        from .stability_provider import StabilityProvider

        return StabilityProvider(settings)
    return None
