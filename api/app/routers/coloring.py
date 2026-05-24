"""Coloring + health routes (architecture §4)."""
from __future__ import annotations

from fastapi import APIRouter, File, Form, UploadFile

from .. import service
from ..config import settings
from ..models import (
    Complexity,
    ColoringResponse,
    FromTextRequest,
    HealthResponse,
    OutputFormat,
)

router = APIRouter(prefix="/api")


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Rich health payload; drives the frontend's Describe-tab gating (FR8/FR11)."""
    return HealthResponse(
        status="ok",
        version="0.1.0",
        text_flow_enabled=settings.text_flow_enabled,
    )


@router.post("/coloring/from-image", response_model=ColoringResponse)
async def from_image(
    file: UploadFile = File(...),
    complexity: Complexity = Form(Complexity.medium),
    output_format: OutputFormat | None = Form(None),
) -> ColoringResponse:
    """Turn an uploaded image into a numbered coloring page (FR1)."""
    raw = await file.read()
    service.validate_upload(file.content_type, raw)
    fmt = output_format.value if output_format else None
    return service.process_image(raw, complexity.value, fmt)


@router.post("/coloring/from-text", response_model=ColoringResponse)
async def from_text(body: FromTextRequest) -> ColoringResponse:
    """Generate an image from a prompt, then make a coloring page (FR2)."""
    fmt = body.output_format.value if body.output_format else None
    return service.process_text(body.prompt, body.complexity.value, fmt)
