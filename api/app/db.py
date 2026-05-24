"""PostgreSQL connection pool and CRUD for the coloring-page library.

Initialised once at startup (main.py lifespan). All functions return
gracefully (None / []) when the pool hasn't been initialised, so the API
stays functional when a DB is not configured.
"""
from __future__ import annotations

import base64
import io

import psycopg2
from psycopg2 import pool
from PIL import Image

_pool: pool.SimpleConnectionPool | None = None

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS coloring_pages (
    id           SERIAL PRIMARY KEY,
    prompt       TEXT,
    category     TEXT NOT NULL DEFAULT 'Other',
    page_image   BYTEA NOT NULL,
    thumbnail    BYTEA,
    source_type  TEXT NOT NULL DEFAULT 'text',
    width        INTEGER,
    height       INTEGER,
    region_count INTEGER,
    created_at   TIMESTAMPTZ DEFAULT NOW()
);
"""


def init(database_url: str) -> None:
    """Create the connection pool and ensure the schema exists."""
    global _pool
    _pool = pool.SimpleConnectionPool(1, 5, database_url)
    conn = _pool.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute(_CREATE_TABLE)
        conn.commit()
    finally:
        _pool.putconn(conn)


def is_ready() -> bool:
    return _pool is not None


# ── helpers ──────────────────────────────────────────────────────────────────

def _make_thumbnail(page_png: bytes, thumb_width: int = 240) -> bytes:
    img = Image.open(io.BytesIO(page_png)).convert("RGB")
    ratio = thumb_width / img.width
    thumb = img.resize((thumb_width, int(img.height * ratio)), Image.LANCZOS)
    buf = io.BytesIO()
    thumb.save(buf, "JPEG", quality=75)
    return buf.getvalue()


def _b64_jpeg(raw: memoryview | bytes | None) -> str | None:
    if raw is None:
        return None
    return "data:image/jpeg;base64," + base64.b64encode(bytes(raw)).decode()


def _b64_png(raw: memoryview | bytes | None) -> str | None:
    if raw is None:
        return None
    return "data:image/png;base64," + base64.b64encode(bytes(raw)).decode()


# ── write ─────────────────────────────────────────────────────────────────────

def save_page(
    *,
    prompt: str | None,
    category: str,
    page_bytes: bytes,
    source_type: str,
    width: int,
    height: int,
    region_count: int,
) -> int | None:
    """Persist a generated page and return its id, or None if DB unavailable."""
    if _pool is None:
        return None
    try:
        thumb = _make_thumbnail(page_bytes)
        conn = _pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO coloring_pages
                       (prompt, category, page_image, thumbnail,
                        source_type, width, height, region_count)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                       RETURNING id""",
                    (
                        prompt,
                        category,
                        psycopg2.Binary(page_bytes),
                        psycopg2.Binary(thumb),
                        source_type,
                        width,
                        height,
                        region_count,
                    ),
                )
                row = cur.fetchone()
            conn.commit()
            return row[0]
        finally:
            _pool.putconn(conn)
    except Exception:
        return None


# ── read ──────────────────────────────────────────────────────────────────────

def list_pages(
    category: str | None = None,
    limit: int = 24,
    offset: int = 0,
) -> list[dict]:
    """Return thumbnail-only rows for the gallery (no full page_image)."""
    if _pool is None:
        return []
    conn = _pool.getconn()
    try:
        with conn.cursor() as cur:
            if category and category.lower() != "all":
                cur.execute(
                    """SELECT id, prompt, category, thumbnail,
                              source_type, width, height, region_count, created_at
                       FROM coloring_pages
                       WHERE category = %s
                       ORDER BY created_at DESC
                       LIMIT %s OFFSET %s""",
                    (category, limit, offset),
                )
            else:
                cur.execute(
                    """SELECT id, prompt, category, thumbnail,
                              source_type, width, height, region_count, created_at
                       FROM coloring_pages
                       ORDER BY created_at DESC
                       LIMIT %s OFFSET %s""",
                    (limit, offset),
                )
            rows = cur.fetchall()
    finally:
        _pool.putconn(conn)

    return [
        {
            "id": r[0],
            "prompt": r[1],
            "category": r[2],
            "thumbnail": _b64_jpeg(r[3]),
            "source_type": r[4],
            "width": r[5],
            "height": r[6],
            "region_count": r[7],
            "created_at": r[8].isoformat() if r[8] else None,
        }
        for r in rows
    ]


def get_page(page_id: int) -> dict | None:
    """Return the full page (with page_image) for a single entry."""
    if _pool is None:
        return None
    conn = _pool.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT id, prompt, category, page_image,
                          source_type, width, height, region_count, created_at
                   FROM coloring_pages
                   WHERE id = %s""",
                (page_id,),
            )
            r = cur.fetchone()
    finally:
        _pool.putconn(conn)

    if r is None:
        return None
    return {
        "id": r[0],
        "prompt": r[1],
        "category": r[2],
        "page_image": _b64_png(r[3]),
        "source_type": r[4],
        "width": r[5],
        "height": r[6],
        "region_count": r[7],
        "created_at": r[8].isoformat() if r[8] else None,
    }


def list_categories() -> list[dict]:
    """Return all categories with their page counts."""
    if _pool is None:
        return []
    conn = _pool.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT category, COUNT(*) AS cnt
                   FROM coloring_pages
                   GROUP BY category
                   ORDER BY cnt DESC"""
            )
            rows = cur.fetchall()
    finally:
        _pool.putconn(conn)

    return [{"category": r[0], "count": r[1]} for r in rows]
