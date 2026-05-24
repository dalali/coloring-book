"""Glue between the API routes and the processing/generation cores (architecture §4).

Keeps the router thin: validation, building the data-URL response, and mapping
domain errors to the standard error envelope live here.

Library additions:
  - Every successful generation is persisted to the DB (non-fatal if DB is down).
  - process_inspire() adds a Vision → DALL-E step so uploaded images are always
    regenerated as clean, kids-friendly coloring-book art before being pipelined.
"""
from __future__ import annotations

import base64

from . import db, errors
from .categorizer import categorize
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

# ── response helpers ──────────────────────────────────────────────────────────

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


def _save(
    result: ColoringResult,
    *,
    prompt: str | None,
    source_type: str,
) -> None:
    """Persist a result to the library (best-effort; never raises)."""
    try:
        category = categorize(prompt, settings.openai_api_key)
        db.save_page(
            prompt=prompt,
            category=category,
            page_bytes=result.page_bytes,
            source_type=source_type,
            width=result.width,
            height=result.height,
            region_count=result.region_count,
        )
    except Exception:
        pass  # library save is best-effort


# ── validation ────────────────────────────────────────────────────────────────

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


# ── AI style prefix ───────────────────────────────────────────────────────────

_COLORING_STYLE = (
    "Coloring book illustration: thick black outlines, flat areas of solid color, "
    "no gradients or shading, no photorealism, white background, clean simple cartoon "
    "style suitable for children to color in. Subject: "
)


# ── vision helper ─────────────────────────────────────────────────────────────

def _describe_image_with_vision(raw: bytes) -> str | None:
    """Use GPT-4o Vision to get a coloring-book description of an uploaded image."""
    if not settings.openai_api_key:
        return None
    try:
        from openai import OpenAI

        client = OpenAI(
            api_key=settings.openai_api_key,
            timeout=settings.generation_timeout_s,
        )
        # Detect mime
        if raw[:4] == b"\x89PNG":
            mime = "image/png"
        elif raw[:6] in (b"GIF87a", b"GIF89a"):
            mime = "image/gif"
        elif raw[:4] == b"RIFF":
            mime = "image/webp"
        else:
            mime = "image/jpeg"

        b64 = base64.b64encode(raw).decode("ascii")
        resp = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{mime};base64,{b64}"},
                        },
                        {
                            "type": "text",
                            "text": (
                                "Describe the main subject of this image in 1-2 sentences, "
                                "suitable for creating a children's coloring book illustration. "
                                "Focus on the main subject, style, and composition. "
                                "Keep it simple and child-friendly."
                            ),
                        },
                    ],
                }
            ],
            max_tokens=150,
        )
        return resp.choices[0].message.content.strip()
    except Exception:
        return None


# ── public service functions ──────────────────────────────────────────────────

def process_image(raw: bytes, complexity: str, output_format: str | None) -> ColoringResponse:
    """Run the pipeline directly on uploaded bytes (FR1).

    Saves the result to the library with source_type='image'.
    Category defaults to 'Other' since we have no text description.
    """
    try:
        result = pipeline.run(raw, complexity, settings, output_format)
    except ValueError as exc:
        raise errors.unreadable_image() from exc
    _save(result, prompt=None, source_type="image")
    return _to_response(result)


def process_inspire(raw: bytes, complexity: str, output_format: str | None) -> ColoringResponse:
    """Use an uploaded image as inspiration (FR1-enhanced).

    If an OpenAI key is available:
      1. GPT-4o Vision describes the image.
      2. DALL-E 3 regenerates it in clean coloring-book style.
      3. The pipeline processes the generated image.
    Falls back to direct pipeline when no key is configured.

    All results are saved to the library.
    """
    description = _describe_image_with_vision(raw)

    provider = get_provider(settings)
    if provider is not None and description:
        # AI-enhanced path: regenerate as clean coloring-book art
        generation_prompt = _COLORING_STYLE + description
        try:
            raw = provider.generate(generation_prompt, size=settings.generation_size)
        except ContentPolicyError as exc:
            raise errors.content_policy(str(exc)) from exc
        except GenerationUnavailable as exc:
            raise errors.generation_unavailable(str(exc)) from exc

    try:
        result = pipeline.run(raw, complexity, settings, output_format)
    except ValueError as exc:
        raise errors.unreadable_image() from exc

    _save(result, prompt=description, source_type="inspire")
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

    generation_prompt = _COLORING_STYLE + prompt

    try:
        raw = provider.generate(generation_prompt, size=settings.generation_size)
    except ContentPolicyError as exc:
        raise errors.content_policy(str(exc)) from exc
    except GenerationUnavailable as exc:
        raise errors.generation_unavailable(str(exc)) from exc

    try:
        result = pipeline.run(raw, complexity, settings, output_format)
    except ValueError as exc:
        raise errors.generation_unavailable("The generated image could not be processed.") from exc

    _save(result, prompt=prompt, source_type="text")
    return _to_response(result)
