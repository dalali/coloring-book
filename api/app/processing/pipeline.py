"""Pipeline orchestrator: raster bytes -> ColoringResult (architecture §5).

Both API front doors (from-image, from-text) converge here. Pure and
network-free so it is unit-testable in isolation (NFR5).
"""
from __future__ import annotations

import io
from dataclasses import dataclass

import numpy as np
from PIL import Image

from ..config import COMPLEXITY_PRESETS, DEFAULT_COMPLEXITY, Settings
from . import quantize as q
from . import regions as rg
from . import render as rnd
from .numbering import compute_labels
from .palette import PaletteColor, build_legend


@dataclass
class ColoringResult:
    page_bytes: bytes          # PNG bytes, or SVG bytes (utf-8) when format == svg
    format: str                # "png" | "svg"
    width: int
    height: int
    legend: list[tuple[int, PaletteColor]]   # (number, color)
    region_count: int
    source_preview_png: bytes  # downscaled source thumbnail as PNG


def _source_preview_png(rgb: np.ndarray) -> bytes:
    img = Image.fromarray(rgb, "RGB")
    img.thumbnail((512, 512), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def run(
    raster_bytes: bytes,
    complexity: str,
    settings: Settings,
    output_format: str | None = None,
) -> ColoringResult:
    """Execute the full pipeline.

    Raises ValueError if the image cannot be decoded (mapped to 422 upstream).
    """
    preset = COMPLEXITY_PRESETS.get(complexity, COMPLEXITY_PRESETS[DEFAULT_COMPLEXITY])
    fmt = (output_format or settings.output_format or "png").lower()
    if fmt not in {"png", "svg"}:
        fmt = "png"

    # (a) decode  (b) downscale + smooth  (c) quantize
    rgb = q.decode_to_rgb(raster_bytes)
    source_preview = _source_preview_png(rgb)
    work = q.downscale(rgb, settings.proc_max_px)
    work = q.smooth(work, preset.smoothing)
    cluster_labels, centers = q.quantize(work, preset.colors)

    # (d) region labeling  (e) clean tiny regions
    region_map = rg.label_regions(cluster_labels)
    total_px = work.shape[0] * work.shape[1]
    min_area = max(1, int(preset.min_region_frac * total_px))
    region_map, cluster_per_region = rg.merge_small_regions(region_map, cluster_labels, min_area)

    # (h) palette mapping: number clusters darkest->lightest.
    used_clusters = sorted({int(c) for c in cluster_per_region.tolist()})
    cluster_lum = {
        c: float(0.2126 * centers[c][0] + 0.7152 * centers[c][1] + 0.0722 * centers[c][2])
        for c in used_clusters
    }
    ordered = sorted(used_clusters, key=lambda c: cluster_lum[c])
    palette = build_legend([cluster_lum[c] for c in ordered])
    cluster_to_number = {c: i + 1 for i, c in enumerate(ordered)}
    cluster_to_color = {c: palette[i] for i, c in enumerate(ordered)}
    legend = [(cluster_to_number[c], cluster_to_color[c]) for c in ordered]

    # (g) numbering anchors
    labels = compute_labels(region_map, cluster_per_region)
    region_count = len({int(r) for r in np.unique(region_map) if r >= 0})

    # (f, i) render + encode
    if fmt == "svg":
        svg = rnd.render_svg(
            region_map, labels, cluster_to_number, legend,
            settings.page_width, settings.page_height,
        )
        page_bytes = svg.encode("utf-8")
        width, height = settings.page_width, settings.page_height
    else:
        artwork = rnd.render_artwork(region_map, labels, cluster_to_number)
        page = rnd.compose_page(artwork, legend, settings.page_width, settings.page_height)
        page_bytes = rnd.encode_png(page)
        width, height = page.width, page.height

    return ColoringResult(
        page_bytes=page_bytes,
        format=fmt,
        width=width,
        height=height,
        legend=legend,
        region_count=region_count,
        source_preview_png=source_preview,
    )
