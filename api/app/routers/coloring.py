"""Coloring, inspire, and library routes (architecture §4)."""
from __future__ import annotations

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from .. import db, service
from ..config import settings
from ..models import (
    CategoryCount,
    Complexity,
    ColoringResponse,
    FromTextRequest,
    HealthResponse,
    LibraryListResponse,
    LibraryPage,
    LibraryPageFull,
    OutputFormat,
)

router = APIRouter(prefix="/api")


# ── health ────────────────────────────────────────────────────────────────────

@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Rich health payload; drives the frontend's tab gating (FR8/FR11)."""
    return HealthResponse(
        status="ok",
        version="0.1.0",
        text_flow_enabled=settings.text_flow_enabled,
        library_enabled=db.is_ready(),
    )


# ── creation ──────────────────────────────────────────────────────────────────

@router.post("/coloring/from-image", response_model=ColoringResponse)
async def from_image(
    file: UploadFile = File(...),
    complexity: Complexity = Form(Complexity.medium),
    output_format: OutputFormat | None = Form(None),
) -> ColoringResponse:
    """Direct pipeline on an uploaded image (FR1, kept for backward compat)."""
    raw = await file.read()
    service.validate_upload(file.content_type, raw)
    fmt = output_format.value if output_format else None
    return service.process_image(raw, complexity.value, fmt)


@router.post("/coloring/from-inspire", response_model=ColoringResponse)
async def from_inspire(
    file: UploadFile = File(...),
    complexity: Complexity = Form(Complexity.medium),
    output_format: OutputFormat | None = Form(None),
) -> ColoringResponse:
    """Use an uploaded image as inspiration.

    If an OpenAI key is configured, GPT-4o Vision describes the image and
    DALL-E 3 regenerates it as clean coloring-book art before pipelining.
    Falls back to direct pipeline when no key is set.
    """
    raw = await file.read()
    service.validate_upload(file.content_type, raw)
    fmt = output_format.value if output_format else None
    return service.process_inspire(raw, complexity.value, fmt)


@router.post("/coloring/from-text", response_model=ColoringResponse)
async def from_text(body: FromTextRequest) -> ColoringResponse:
    """Generate an image from a prompt, then make a coloring page (FR2)."""
    fmt = body.output_format.value if body.output_format else None
    return service.process_text(body.prompt, body.complexity.value, fmt)


# ── library ───────────────────────────────────────────────────────────────────

@router.get("/library/categories", response_model=list[CategoryCount])
def library_categories() -> list[CategoryCount]:
    """Return all categories with their page counts."""
    rows = db.list_categories()
    return [CategoryCount(**r) for r in rows]


@router.get("/library/{page_id}", response_model=LibraryPageFull)
def library_page(page_id: int) -> LibraryPageFull:
    """Return the full coloring page (with page_image data URL)."""
    row = db.get_page(page_id)
    if row is None:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Page not found."})
    return LibraryPageFull(**row)


@router.get("/library", response_model=LibraryListResponse)
def library_list(
    category: str | None = None,
    limit: int = 24,
    offset: int = 0,
) -> LibraryListResponse:
    """Paginated gallery. Filter by category (omit or 'all' for everything)."""
    limit = min(limit, 48)  # safety cap
    rows = db.list_pages(category=category, limit=limit, offset=offset)
    pages = [LibraryPage(**r) for r in rows]
    return LibraryListResponse(pages=pages, total_shown=len(pages))
