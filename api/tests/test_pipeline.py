"""Unit tests for the image-processing pipeline (NFR5).

Pure, network-free, deterministic (seeded k-means).
"""
from __future__ import annotations

import io

import numpy as np
import pytest
from PIL import Image

from app.config import settings
from app.processing import pipeline


def _decode_png(b: bytes) -> Image.Image:
    return Image.open(io.BytesIO(b))


def test_multicolor_produces_legend_and_regions(multicolor_png):
    result = pipeline.run(multicolor_png, "simple", settings, output_format="png")
    assert result.format == "png"
    assert result.region_count >= 4          # four quadrants
    assert len(result.legend) >= 2
    # Legend numbers are contiguous starting at 1.
    numbers = sorted(n for n, _ in result.legend)
    assert numbers == list(range(1, len(numbers) + 1))
    # Page decodes and matches configured print size.
    img = _decode_png(result.page_bytes)
    assert (img.width, img.height) == (settings.page_width, settings.page_height)
    # Source preview is a valid PNG.
    assert _decode_png(result.source_preview_png).size[0] > 0


def test_single_color_image_does_not_crash(single_color_png):
    result = pipeline.run(single_color_png, "medium", settings, output_format="png")
    assert result.region_count >= 1
    assert len(result.legend) >= 1
    assert len(result.page_bytes) > 0


def test_deterministic_region_count(multicolor_png):
    r1 = pipeline.run(multicolor_png, "medium", settings, output_format="png")
    r2 = pipeline.run(multicolor_png, "medium", settings, output_format="png")
    assert r1.region_count == r2.region_count
    assert [n for n, _ in r1.legend] == [n for n, _ in r2.legend]


def test_svg_output(multicolor_png):
    result = pipeline.run(multicolor_png, "simple", settings, output_format="svg")
    assert result.format == "svg"
    svg = result.page_bytes.decode("utf-8")
    assert svg.startswith("<svg")
    assert "</svg>" in svg
    assert "<polygon" in svg or "<text" in svg


def test_unreadable_bytes_raise_value_error():
    with pytest.raises(ValueError):
        pipeline.run(b"not an image", "medium", settings)


def test_complexity_increases_detail(multicolor_png):
    simple = pipeline.run(multicolor_png, "simple", settings)
    detailed = pipeline.run(multicolor_png, "detailed", settings)
    # Detailed should not yield fewer regions than simple.
    assert detailed.region_count >= simple.region_count
