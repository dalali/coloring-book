"""Named color palettes per complexity level (architecture §5h, AD5).

MVP maps quantized clusters to a fixed, human-readable named palette by ordering
clusters from darkest to lightest (luminance) and pairing them with palette
entries also ordered by luminance. This yields a legible legend without true
source-color extraction (a documented fast-follow).
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PaletteColor:
    name: str
    hex: str

    @property
    def rgb(self) -> tuple[int, int, int]:
        h = self.hex.lstrip("#")
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)

    @property
    def luminance(self) -> float:
        r, g, b = self.rgb
        return 0.2126 * r + 0.7152 * g + 0.0722 * b


# A broad named palette (20 colors) covering the spectrum. The first N (ordered
# by luminance) are used for a given complexity level.
_PALETTE: list[PaletteColor] = [
    PaletteColor("Black", "#1F2937"),
    PaletteColor("Charcoal", "#374151"),
    PaletteColor("Brown", "#92400E"),
    PaletteColor("Dark Red", "#991B1B"),
    PaletteColor("Red", "#E11D48"),
    PaletteColor("Orange", "#F97316"),
    PaletteColor("Amber", "#F59E0B"),
    PaletteColor("Olive", "#65A30D"),
    PaletteColor("Green", "#16A34A"),
    PaletteColor("Teal", "#0D9488"),
    PaletteColor("Cyan", "#06B6D4"),
    PaletteColor("Blue", "#2563EB"),
    PaletteColor("Indigo", "#4F46E5"),
    PaletteColor("Purple", "#7C3AED"),
    PaletteColor("Magenta", "#C026D3"),
    PaletteColor("Pink", "#EC4899"),
    PaletteColor("Sky Blue", "#38BDF8"),
    PaletteColor("Lime", "#A3E635"),
    PaletteColor("Sand", "#FCD34D"),
    PaletteColor("White", "#F9FAFB"),
]


def build_legend(cluster_luminances: list[float]) -> list[PaletteColor]:
    """Map quantized clusters (given their luminances) to named palette colors.

    Clusters are sorted darkest -> lightest and paired with palette colors also
    sorted darkest -> lightest, so number ``n`` always corresponds to the same
    ordering. Returns one PaletteColor per cluster, indexed by the cluster's
    *luminance rank* (0 = darkest).

    The returned list length equals ``len(cluster_luminances)``.
    """
    k = len(cluster_luminances)
    if k <= 0:
        return []

    palette_sorted = sorted(_PALETTE, key=lambda c: c.luminance)

    if k <= len(palette_sorted):
        # Evenly sample the palette across its luminance range so a small K still
        # spans dark->light rather than clustering at one end.
        step = (len(palette_sorted) - 1) / max(k - 1, 1) if k > 1 else 0
        chosen = [palette_sorted[round(i * step)] for i in range(k)]
        return chosen

    # More clusters than named colors: reuse by wrapping (rare; detailed level
    # caps at 20 == palette size).
    return [palette_sorted[i % len(palette_sorted)] for i in range(k)]
