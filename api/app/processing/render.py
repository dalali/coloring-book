"""Compose the B&W outline + numbers + legend into a printable page.

Outputs PNG (always-on default) or SVG (config-gated). The page is sized to a
print aspect (Letter @ ~150 DPI by default) with the artwork fit into the top
area and a color legend rendered beneath it, so the downloaded file is
self-contained (architecture §5.3).
"""
from __future__ import annotations

import io
import xml.sax.saxutils as sax

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .numbering import RegionLabel
from .palette import PaletteColor

OUTLINE_COLOR = (31, 41, 55)  # near-black
SWATCH = 28
LEGEND_PAD = 24


def _outline_mask(region_map: np.ndarray) -> np.ndarray:
    """Boolean HxW mask: True on pixels at a boundary between two regions."""
    rm = region_map
    diff = np.zeros(rm.shape, dtype=bool)
    diff[:, :-1] |= rm[:, :-1] != rm[:, 1:]
    diff[:, 1:] |= rm[:, :-1] != rm[:, 1:]
    diff[:-1, :] |= rm[:-1, :] != rm[1:, :]
    diff[1:, :] |= rm[:-1, :] != rm[1:, :]
    return diff


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def render_artwork(
    region_map: np.ndarray,
    labels: list[RegionLabel],
    luminance_rank: dict[int, int],
) -> Image.Image:
    """Render the white page with black outlines and printed numbers.

    ``luminance_rank`` maps cluster index -> the 1-based number to print.
    """
    h, w = region_map.shape
    canvas = np.full((h, w, 3), 255, dtype=np.uint8)
    mask = _outline_mask(region_map)
    canvas[mask] = OUTLINE_COLOR

    img = Image.fromarray(canvas, "RGB")
    draw = ImageDraw.Draw(img)

    for lab in labels:
        if not lab.labelable:
            continue
        number = luminance_rank[lab.cluster]
        font_size = max(10, min(int(lab.radius * 1.2), 40))
        font = _load_font(font_size)
        text = str(number)
        bbox = draw.textbbox((0, 0), text, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        draw.text(
            (lab.x - tw / 2 - bbox[0], lab.y - th / 2 - bbox[1]),
            text,
            fill=OUTLINE_COLOR,
            font=font,
        )
    return img


def compose_page(
    artwork: Image.Image,
    legend: list[tuple[int, PaletteColor]],
    page_w: int,
    page_h: int,
) -> Image.Image:
    """Fit artwork into a print page and draw the legend beneath it."""
    page = Image.new("RGB", (page_w, page_h), (255, 255, 255))
    draw = ImageDraw.Draw(page)

    legend_rows = (len(legend) + 1) // 2
    legend_h = LEGEND_PAD * 2 + legend_rows * (SWATCH + 8)
    art_area_h = max(1, page_h - legend_h)

    # Fit artwork (letterbox) into the top area.
    scale = min(page_w / artwork.width, art_area_h / artwork.height)
    aw = max(1, int(artwork.width * scale))
    ah = max(1, int(artwork.height * scale))
    resized = artwork.resize((aw, ah), Image.LANCZOS)
    page.paste(resized, ((page_w - aw) // 2, (art_area_h - ah) // 2))

    # Legend: two columns.
    font = _load_font(20)
    y0 = art_area_h + LEGEND_PAD
    col_w = (page_w - LEGEND_PAD * 2) // 2
    for i, (n, color) in enumerate(legend):
        col = i % 2
        row = i // 2
        x = LEGEND_PAD + col * col_w
        y = y0 + row * (SWATCH + 8)
        draw.rectangle([x, y, x + SWATCH, y + SWATCH], fill=color.rgb, outline=OUTLINE_COLOR)
        draw.text((x + SWATCH + 10, y + 3), f"{n}. {color.name}", fill=OUTLINE_COLOR, font=font)
    return page


def encode_png(page: Image.Image) -> bytes:
    buf = io.BytesIO()
    page.save(buf, format="PNG")
    return buf.getvalue()


def render_svg(
    region_map: np.ndarray,
    labels: list[RegionLabel],
    luminance_rank: dict[int, int],
    legend: list[tuple[int, PaletteColor]],
    page_w: int,
    page_h: int,
) -> str:
    """Emit an SVG with region contours + number text + legend.

    No external references (sanitized; architecture §9 security note).
    """
    h, w = region_map.shape
    legend_rows = (len(legend) + 1) // 2
    legend_h = LEGEND_PAD * 2 + legend_rows * (SWATCH + 8)
    art_area_h = max(1, page_h - legend_h)
    scale = min(page_w / w, art_area_h / h)
    aw, ah = w * scale, h * scale
    off_x = (page_w - aw) / 2
    off_y = (art_area_h - ah) / 2

    parts: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{page_w}" height="{page_h}" '
        f'viewBox="0 0 {page_w} {page_h}">',
        f'<rect width="{page_w}" height="{page_h}" fill="#ffffff"/>',
        f'<g transform="translate({off_x:.2f},{off_y:.2f}) scale({scale:.4f})">',
    ]

    # Contours per region as stroked paths.
    for rid in [int(r) for r in np.unique(region_map) if r >= 0]:
        mask = (region_map == rid).astype(np.uint8)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for cnt in contours:
            if len(cnt) < 2:
                continue
            pts = " ".join(f"{int(p[0][0])},{int(p[0][1])}" for p in cnt)
            parts.append(f'<polygon points="{pts}" fill="none" stroke="#1F2937" stroke-width="2"/>')

    for lab in labels:
        if not lab.labelable:
            continue
        number = luminance_rank[lab.cluster]
        size = max(10, min(int(lab.radius * 1.2), 40))
        parts.append(
            f'<text x="{lab.x}" y="{lab.y}" font-size="{size}" font-family="sans-serif" '
            f'fill="#1F2937" text-anchor="middle" dominant-baseline="central">{number}</text>'
        )
    parts.append("</g>")

    # Legend.
    col_w = (page_w - LEGEND_PAD * 2) / 2
    for i, (n, color) in enumerate(legend):
        col = i % 2
        row = i // 2
        x = LEGEND_PAD + col * col_w
        y = art_area_h + LEGEND_PAD + row * (SWATCH + 8)
        label = sax.escape(f"{n}. {color.name}")
        parts.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{SWATCH}" height="{SWATCH}" '
                     f'fill="{color.hex}" stroke="#1F2937"/>')
        parts.append(f'<text x="{x + SWATCH + 10:.1f}" y="{y + 20:.1f}" font-size="20" '
                     f'font-family="sans-serif" fill="#1F2937">{label}</text>')

    parts.append("</svg>")
    return "".join(parts)
