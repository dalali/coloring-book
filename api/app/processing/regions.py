"""Connected-component region labeling and small-region cleanup.

Takes the per-pixel cluster label map from quantization and produces a clean
region map where each connected same-cluster blob is its own region, with tiny
regions merged into their largest neighbor (architecture §5 d-e).
"""
from __future__ import annotations

import numpy as np
from scipy import ndimage as ndi


def label_regions(cluster_labels: np.ndarray) -> np.ndarray:
    """Connected-components within each cluster.

    Two pixels share a region only if they are 4-connected *and* belong to the
    same cluster. Returns an HxW int array of region ids starting at 0.
    """
    h, w = cluster_labels.shape
    region_map = np.full((h, w), -1, dtype=np.int32)
    next_id = 0
    structure = np.array([[0, 1, 0], [1, 1, 1], [0, 1, 0]], dtype=np.int32)

    for cluster in np.unique(cluster_labels):
        mask = cluster_labels == cluster
        labeled, count = ndi.label(mask, structure=structure)
        for comp in range(1, count + 1):
            region_map[labeled == comp] = next_id
            next_id += 1
    return region_map


def _neighbor_regions(region_map: np.ndarray, target: int) -> set[int]:
    """Region ids 4-adjacent to ``target``."""
    mask = region_map == target
    neighbors: set[int] = set()
    # Shift the mask in four directions and read the bordering region ids.
    for shift, axis in ((1, 0), (-1, 0), (1, 1), (-1, 1)):
        rolled = np.roll(mask, shift, axis=axis)
        border = region_map[rolled & ~mask]
        for rid in np.unique(border):
            if rid != target and rid >= 0:
                neighbors.add(int(rid))
    return neighbors


def merge_small_regions(
    region_map: np.ndarray,
    cluster_labels: np.ndarray,
    min_area: int,
) -> tuple[np.ndarray, np.ndarray]:
    """Merge regions smaller than ``min_area`` into their largest neighbor.

    Returns ``(new_region_map, new_cluster_per_region)`` where the second value
    maps each *remaining* region id to its cluster index. Region ids are
    re-compacted to 0..R-1. Guarantees at least one region remains.
    """
    region_map = region_map.copy()

    # Iterate until no small regions remain or no further merge is possible.
    changed = True
    while changed:
        changed = False
        ids, counts = np.unique(region_map[region_map >= 0], return_counts=True)
        if len(ids) <= 1:
            break
        areas = dict(zip(ids.tolist(), counts.tolist()))
        # Process smallest first.
        for rid in sorted(areas, key=lambda r: areas[r]):
            if areas[rid] >= min_area:
                continue
            neighbors = _neighbor_regions(region_map, rid)
            if not neighbors:
                continue
            # Merge into the largest neighbor.
            target = max(neighbors, key=lambda n: areas.get(n, 0))
            region_map[region_map == rid] = target
            changed = True
            break  # recompute areas after each merge

    # Re-compact ids and record the cluster for each surviving region.
    old_ids = [int(r) for r in np.unique(region_map) if r >= 0]
    remap = {old: new for new, old in enumerate(old_ids)}
    compact = np.full_like(region_map, -1)
    cluster_per_region = np.zeros(len(old_ids), dtype=np.int32)
    for old, new in remap.items():
        mask = region_map == old
        compact[mask] = new
        # All pixels in a region share a cluster; take the first.
        cluster_per_region[new] = int(cluster_labels[mask][0])

    return compact, cluster_per_region
