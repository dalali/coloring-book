"""Glue between the API routes and the processing/generation cores (architecture §4).

Keeps the router thin: validation, building the data-URL response, and mapping
domain errors to the standard error envelope live here.
"""
from __future__ import annotations

import base64

from . import errors
from .config import settings
from .generation.base import (
    ContentPolicyError,
    GenerationUnavailable,
    get_provider,
)
from .models import ColoringResponse, LegendEntry
from .processing import pipeline
from .processing.pipeline import ColoringResult

ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/jpg", "image/png", "image/webp"}
MAX_PROMPT_CHARS = 1000


def _data_url(raw: bytes, fmt: str) -> str:
    mime = "image/svg+xml" if fmt == "svg" else "image/png"
    b64 = base64.b64encode(raw).decode("ascii")
    return f"data:{mime};base64,{b64}"


def _to_response(result: ColoringResult) -> ColoringResponse:
    return ColoringResponse(
        page_image=_data_url(result.page_bytes, result.format),
        format=result.format,
        width=result.width,
        height=result.height,
        legend=[LegendEntry(n=n, name=c.name, hex=c.hex) for n, c in result.legend],
        region_count=result.region_count,
        source_preview=_data_url(result.source_preview_png, "png"),
    )


def validate_upload(content_type: str | None, raw: bytes) -> None:
    """Validate an uploaded image's type and size (FR7, architecture §4.4)."""
    ctype = (content_type or "").split(";")[0].strip().lower()
    if ctype not in ALLOWED_CONTENT_TYPES:
        raise errors.unsupported_type()
    if len(raw) > settings.max_image_size_bytes:
        mb = len(raw) / (1024 * 1024)
        raise errors.file_too_large(
            f"That file is {mb:.1f} MB — the max is {settings.max_image_size_mb} MB."
        )
    if not raw:
        raise errors.unreadable_image("The uploaded file was empty.")


def process_image(raw: bytes, complexity: str, output_format: str | None) -> ColoringResponse:
    """Run the pipeline on uploaded bytes (FR1)."""
    try:
        result = pipeline.run(raw, complexity, settings, output_format)
    except ValueError as exc:
        raise errors.unreadable_image() from exc
    return _to_response(result)


def process_text(prompt: str, complexity: str, output_format: str | None) -> ColoringResponse:
    """Generate an image from a prompt, then run the pipeline (FR2)."""
    prompt = (prompt or "").strip()
    if not prompt:
        raise errors.empty_prompt()
    prompt = prompt[:MAX_PROMPT_CHARS]

    provider = get_provider(settings)
    if provider is None:
        raise errors.text_flow_disabled()

    try:
        raw = provider.generate(prompt, size=settings.generation_size)
    except ContentPolicyError as exc:
        raise errors.content_policy(str(exc)) from exc
    except GenerationUnavailable as exc:
        raise errors.generation_unavailable(str(exc)) from exc

    try:
        result = pipeline.run(raw, complexity, settings, output_format)
    except ValueError as exc:
        raise errors.generation_unavailable("The generated image could not be processed.") from exc
    return _to_response(result)
