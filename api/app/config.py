"""Typed application settings, read once from the environment.

No secrets are ever logged or returned to clients (NFR3 / R5). The frontend only
ever learns the boolean ``text_flow_enabled`` derived from whether a provider key
is configured.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class ComplexityPreset:
    """Pipeline tuning for a single complexity level (architecture §5.1)."""

    colors: int          # K for k-means / target palette size
    smoothing: int       # bilateral blur strength (higher = simpler)
    min_region_frac: float  # min region area as a fraction of total pixels


COMPLEXITY_PRESETS: dict[str, ComplexityPreset] = {
    "simple": ComplexityPreset(colors=6, smoothing=9, min_region_frac=0.010),
    "medium": ComplexityPreset(colors=12, smoothing=5, min_region_frac=0.004),
    "detailed": ComplexityPreset(colors=20, smoothing=2, min_region_frac=0.0015),
}

DEFAULT_COMPLEXITY = "medium"


@dataclass(frozen=True)
class Settings:
    app_env: str = "development"
    debug: bool = True

    # Image processing limits / output (architecture §9, AD7)
    max_image_size_mb: int = 10
    output_format: str = "png"        # png | svg
    proc_max_px: int = 1024           # longest side after downscale
    page_width: int = 1275            # Letter @ ~150 DPI
    page_height: int = 1650

    # AI generation
    openai_api_key: str | None = None
    stability_api_key: str | None = None
    generation_timeout_s: int = 90
    generation_size: int = 1024

    # Database
    database_url: str | None = None

    # CORS
    allowed_origins: list[str] = field(default_factory=lambda: ["http://localhost:3000"])

    @property
    def max_image_size_bytes(self) -> int:
        return self.max_image_size_mb * 1024 * 1024

    @property
    def text_flow_enabled(self) -> bool:
        """True when at least one AI provider key is configured (FR11)."""
        return bool(self.openai_api_key or self.stability_api_key)


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw.strip())
    except ValueError:
        return default


def _clean_key(name: str) -> str | None:
    raw = os.getenv(name)
    if raw is None:
        return None
    raw = raw.strip()
    return raw or None


def load_settings() -> Settings:
    """Build a Settings instance from the current environment."""
    origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000")
    origin_list = [o.strip() for o in origins.split(",") if o.strip()]

    output_format = os.getenv("OUTPUT_FORMAT", "png").strip().lower()
    if output_format not in {"png", "svg"}:
        output_format = "png"

    return Settings(
        app_env=os.getenv("APP_ENV", "development"),
        debug=_env_bool("DEBUG", True),
        max_image_size_mb=_env_int("MAX_IMAGE_SIZE_MB", 10),
        output_format=output_format,
        proc_max_px=_env_int("PROC_MAX_PX", 1024),
        page_width=_env_int("PAGE_WIDTH", 1275),
        page_height=_env_int("PAGE_HEIGHT", 1650),
        openai_api_key=_clean_key("OPENAI_API_KEY"),
        stability_api_key=_clean_key("STABILITY_API_KEY"),
        generation_timeout_s=_env_int("GENERATION_TIMEOUT_S", 30),
        generation_size=_env_int("GENERATION_SIZE", 1024),
        database_url=_clean_key("DATABASE_URL"),
        allowed_origins=origin_list or ["http://localhost:3000"],
    )


# Module-level singleton: settings are read once at import (NFR3).
settings = load_settings()
