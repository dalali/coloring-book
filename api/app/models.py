"""Pydantic request/response models and shared enums (architecture §4)."""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class Complexity(str, Enum):
    simple = "simple"
    medium = "medium"
    detailed = "detailed"


class OutputFormat(str, Enum):
    png = "png"
    svg = "svg"


class FromTextRequest(BaseModel):
    """Body for POST /api/coloring/from-text (FR2)."""

    prompt: str = Field(..., description="Text description of the picture to color.")
    complexity: Complexity = Complexity.medium
    output_format: OutputFormat | None = None


class LegendEntry(BaseModel):
    n: int = Field(..., description="The number printed inside matching regions.")
    name: str = Field(..., description="Human-readable palette color name.")
    hex: str = Field(..., description="Hex color value, e.g. #E11D48.")


class ColoringResponse(BaseModel):
    """Success shape for both coloring endpoints (architecture §4.2)."""

    page_image: str = Field(..., description="data: URL of the rendered page.")
    format: str
    width: int
    height: int
    legend: list[LegendEntry]
    region_count: int
    source_preview: str = Field(..., description="data: URL of the source image.")


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "0.1.0"
    text_flow_enabled: bool = False
    library_enabled: bool = False


class ErrorBody(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorBody


# ── library ───────────────────────────────────────────────────────────────────

class LibraryPage(BaseModel):
    """A single entry in the coloring-page library (thumbnail variant)."""

    id: int
    prompt: str | None
    category: str
    thumbnail: str | None = Field(None, description="JPEG thumbnail as data: URL.")
    source_type: str
    width: int | None
    height: int | None
    region_count: int | None
    created_at: str | None


class LibraryPageFull(BaseModel):
    """Full page returned by GET /api/library/{id}."""

    id: int
    prompt: str | None
    category: str
    page_image: str | None = Field(None, description="Full PNG as data: URL.")
    source_type: str
    width: int | None
    height: int | None
    region_count: int | None
    created_at: str | None


class CategoryCount(BaseModel):
    category: str
    count: int


class LibraryListResponse(BaseModel):
    pages: list[LibraryPage]
    total_shown: int
