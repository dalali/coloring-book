"""Compute a legible label anchor for each region (architecture §5g, §5.2).

The anchor is the distance-transform maximum inside the region, which keeps the
printed number away from borders. Regions too small for legible text are still
returned (with a flag) so the caller can outline them without labeling.
"""
from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np


@dataclass(frozen=True)
class RegionLabel:
    region_id: int
    cluster: int
    x: int
    y: int
    area: int
    radius: float  # distance-transform peak value ~ inscribed-circle radius
    labelable: bool  # False if too small for legible text


def compute_labels(
    region_map: np.ndarray,
    cluster_per_region: np.ndarray,
    min_radius: float = 6.0,
) -> list[RegionLabel]:
    """Return a RegionLabel for every region in ``region_map``.

    ``min_radius`` is the smallest inscribed-circle radius (px) that still fits a
    legible digit; smaller regions are returned with ``labelable=False``.
    """
    labels: list[RegionLabel] = []
    region_ids = [int(r) for r in np.unique(region_map) if r >= 0]

    for rid in region_ids:
        mask = (region_map == rid).astype(np.uint8)
        area = int(mask.sum())
        if area == 0:
            continue
        # Distance transform; peak = deepest interior point.
        dist = cv2.distanceTransform(mask, cv2.DIST_L2, 5)
        _min, max_val, _min_loc, max_loc = cv2.minMaxLoc(dist)
        x, y = int(max_loc[0]), int(max_loc[1])
        labels.append(
            RegionLabel(
                region_id=rid,
                cluster=int(cluster_per_region[rid]),
                x=x,
                y=y,
                area=area,
                radius=float(max_val),
                labelable=max_val >= min_radius,
            )
        )
    return labels
