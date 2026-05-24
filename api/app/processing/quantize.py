"""Decode, downscale, smooth, and color-quantize a source image.

Pure functions over ndarrays — no FastAPI, no network (architecture §5 a-c, NFR5).
K-means is seeded for deterministic output across test runs (architecture §5.4).
"""
from __future__ import annotations

import io

import cv2
import numpy as np
from PIL import Image

KMEANS_SEED = 42


def decode_to_rgb(raster_bytes: bytes) -> np.ndarray:
    """Decode arbitrary image bytes (JPG/PNG/WebP) to an HxWx3 RGB uint8 array.

    Raises ValueError if the bytes cannot be decoded (mapped to 422 upstream).
    """
    try:
        img = Image.open(io.BytesIO(raster_bytes))
        img = img.convert("RGB")
    except Exception as exc:  # Pillow raises a variety of errors
        raise ValueError("Could not decode image") from exc
    return np.asarray(img, dtype=np.uint8)


def downscale(rgb: np.ndarray, max_px: int) -> np.ndarray:
    """Scale so the longest side <= max_px, preserving aspect ratio."""
    h, w = rgb.shape[:2]
    longest = max(h, w)
    if longest <= max_px:
        return rgb
    scale = max_px / float(longest)
    new_w = max(1, int(round(w * scale)))
    new_h = max(1, int(round(h * scale)))
    return cv2.resize(rgb, (new_w, new_h), interpolation=cv2.INTER_AREA)


def smooth(rgb: np.ndarray, strength: int) -> np.ndarray:
    """Flatten texture with an edge-preserving bilateral filter.

    ``strength`` is the diameter; higher = simpler/flatter. 0 disables.
    """
    if strength <= 0:
        return rgb
    d = max(1, int(strength))
    return cv2.bilateralFilter(rgb, d=d, sigmaColor=75, sigmaSpace=75)


def quantize(rgb: np.ndarray, k: int) -> tuple[np.ndarray, np.ndarray]:
    """K-means color quantization.

    Returns ``(labels, centers)`` where:
      - ``labels`` is an HxW int array; each pixel's cluster index.
      - ``centers`` is a Kx3 float array of cluster RGB centroids.

    K is clamped to the number of distinct pixels so degenerate (e.g.
    single-color) images never crash (architecture Edge Cases / §5.4).
    """
    h, w = rgb.shape[:2]
    samples = rgb.reshape(-1, 3).astype(np.float32)

    distinct = np.unique(samples, axis=0)
    effective_k = int(min(max(1, k), len(distinct)))

    if effective_k == 1:
        labels = np.zeros((h, w), dtype=np.int32)
        centers = distinct[:1].astype(np.float32)
        return labels, centers

    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 1.0)
    # Fixed seed for deterministic clustering (architecture §5.4).
    cv2.setRNGSeed(KMEANS_SEED)
    _compactness, labels, centers = cv2.kmeans(
        samples,
        effective_k,
        None,
        criteria,
        attempts=3,
        flags=cv2.KMEANS_PP_CENTERS,
    )
    labels = labels.reshape(h, w).astype(np.int32)
    centers = centers.astype(np.float32)
    return labels, centers
