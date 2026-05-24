"""Shared test fixtures.

We generate small synthetic images in-process (deterministic, no checked-in
binaries) so the pipeline can be exercised network-free (architecture §5.4).
"""
from __future__ import annotations

import io

import numpy as np
import pytest
from PIL import Image


def _to_png_bytes(arr: np.ndarray) -> bytes:
    buf = io.BytesIO()
    Image.fromarray(arr, "RGB").save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture
def multicolor_png() -> bytes:
    """A 120x120 image split into four solid colored quadrants."""
    arr = np.zeros((120, 120, 3), dtype=np.uint8)
    arr[:60, :60] = (220, 30, 60)     # red
    arr[:60, 60:] = (40, 100, 220)    # blue
    arr[60:, :60] = (30, 180, 90)     # green
    arr[60:, 60:] = (240, 200, 60)    # yellow
    return _to_png_bytes(arr)


@pytest.fixture
def single_color_png() -> bytes:
    """A degenerate 64x64 solid image (Edge Cases: must not crash)."""
    arr = np.full((64, 64, 3), 128, dtype=np.uint8)
    return _to_png_bytes(arr)
