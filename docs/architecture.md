# Architecture — coloring-book

**Status:** Draft (iteration 1)
**Author:** Systems Architect (PM pipeline)
**Date:** 2026-05-24
**Sources:** docs/PRD.md, docs/design.md, existing scaffold (api/, frontend/, docker-compose.yml)

---

## 0. Summary & Guiding Decisions

coloring-book turns **an uploaded image or a text prompt** into a **printable
black-and-white, color-by-number page** (numbered closed regions + a color
legend). Two input paths converge on one shared image-processing pipeline:

```
Upload image ─┐
              ├─► [source raster image] ─► PIPELINE ─► numbered page + legend ─► download
Text prompt ──┘        (AI generates)
```

The architecture is deliberately small, **stateless**, and **local-first**
(Docker Compose), matching the PRD non-goals (no auth, no DB, no persistence).

**Architectural decisions (AD), with rationale:**

- **AD1 — Stateless, request-scoped processing.** No database, no session, no
  long-term storage (PRD A1/A9, NFR2). The API receives a source image (uploaded
  or AI-generated in the same request), processes it in memory / a temp dir, and
  returns the result inline. Temp files are deleted before the response returns.
- **AD2 — One pipeline, two front doors.** `from-image` and `from-text` differ
  *only* in how the source raster is obtained. Both call the identical
  `processing` core. This keeps the testable surface tiny (NFR5) and guarantees
  consistent output across both user stories.
- **AD3 — Provider abstraction for AI generation** (PRD FR10). A thin
  `ImageProvider` interface with an `OpenAIProvider` (default) and an optional
  `StabilityProvider`, selected by env. The router never imports a concrete
  provider directly.
- **AD4 — Return results inline as base64 data URLs**, not via stored file URLs.
  Because the API is stateless and stores nothing (AD1), the JSON response
  carries the rendered page (and source preview) as a `data:` URL the browser can
  display and download directly. This avoids a second round-trip and any need for
  a static-file store. (Trade-off discussed in §10.)
- **AD5 — Fixed named palette per complexity level** (PRD A4/A6, OQ1). MVP does
  *not* extract true colors from the source; it quantizes to N clusters and maps
  cluster → a named palette color by luminance ordering. Source-color matching is
  a fast-follow.
- **AD6 — Endpoint prefix `/api`.** The PRD (FR1/FR2/FR8) specifies routes under
  `/api/...` and `GET /api/health`. The current scaffold exposes `/health`. We
  mount an `APIRouter(prefix="/api")` and move health under it, **keeping a
  backward-compatible `/health`** alias so the existing `test_health` test
  continues to pass while satisfying FR8. (See §4 and §11.)
- **AD7 — Cap everything that can blow up CPU/RAM** (NFR7, R3): max upload size,
  max processed resolution (downscale-before-process), and max region count
  (driven by the complexity preset). These caps are the DoS guardrail.

---

## 1. Tech Stack Decisions

### 1.1 Backend — Python 3.11 + FastAPI

| Concern | Choice | Why |
|---------|--------|-----|
| Web framework | **FastAPI 0.115** (scaffolded) | Async, typed, auto OpenAPI docs; `python-multipart` already present for uploads (FR1). |
| ASGI server | **uvicorn[standard] 0.30** (scaffolded) | Standard FastAPI runtime; single worker is enough for local MVP. |
| Image I/O | **Pillow 10.4** (scaffolded) | Decode JPG/PNG/WebP, encode PNG output, draw number labels. |
| Vision / quantization | **OpenCV (headless) 4.10 + NumPy 1.26** (scaffolded) | K-means color quantization, connected-components labeling, contour extraction, morphology for region cleanup. Headless avoids GUI deps in container. |
| Optional CV helpers | **scikit-image 0.24** (scaffolded) | `label`, `regionprops`, small-object removal — cleaner than hand-rolling. Used where it simplifies code; OpenCV is the primary engine. |
| AI client | **openai 1.40** (scaffolded) + **httpx 0.27** | OpenAI Images SDK (default provider); httpx for the optional Stability REST call and for fetching generated image bytes. |
| Tests | **pytest 8.3 + pytest-asyncio** (scaffolded) | Unit tests on pipeline + mocked provider (NFR5). |

No new backend dependencies are required for the MVP — the scaffold's
`requirements.txt` already covers the full pipeline and both providers.

### 1.2 Frontend — React 18 + Vite 5

| Concern | Choice | Why |
|---------|--------|-----|
| Framework / bundler | **React 18 + Vite 5** (scaffolded) | Fast dev server on :3000; matches design's component breakdown (design §7). |
| HTTP | **`fetch`** (no axios) | Single-screen app, a couple of endpoints — native fetch is enough (Rule: simplicity first). |
| State | **React local state (`useState`/`useReducer`)** | No routing, no global store needed (design DA5: single-page, no auth). A small reducer models the UI state machine (design §5). |
| Styling | **Plain CSS + CSS variables** | Design tokens (design §6.1) map 1:1 to CSS custom properties; no Tailwind/CSS-in-JS needed for one screen. |
| API base URL | **`import.meta.env.VITE_API_URL`** (already wired in compose) | Decouples frontend from API host. |

No new frontend runtime dependencies for MVP. (`@vitejs/plugin-react` dev dep is
already present.)

### 1.3 Infrastructure — Docker Compose

Two services (`api`, `frontend`) already defined in `docker-compose.yml`, both
reading `.env`. `run.sh` already implements the project-standard command set
(start/stop/restart/logs/build/status/test/shell/clean/help). No infra changes
required beyond what the scaffold provides; deployment detail in §8.

---

## 2. Component Architecture (backend)

Logical module layout under `api/app/` (extends the existing scaffold —
`processing/` and `generation/` packages already exist as empty `__init__.py`):

```
api/app/
├── main.py                 # FastAPI app, CORS, router mounting, health
├── config.py               # (new) typed settings from env (size, format, palette, origins, provider)
├── routers/
│   ├── __init__.py
│   └── coloring.py         # (new) /api/coloring/from-image, /api/coloring/from-text, /api/health
├── models.py               # (new) Pydantic request/response models + Complexity enum
├── processing/             # IMAGE PIPELINE (pure, network-free — NFR5)
│   ├── __init__.py
│   ├── pipeline.py         # (new) orchestrator: raster bytes -> ColoringResult
│   ├── quantize.py         # (new) downscale + k-means color quantization
│   ├── regions.py          # (new) label regions, merge tiny ones, contours
│   ├── numbering.py        # (new) place number labels per region
│   ├── palette.py          # (new) named-color palette per complexity
│   └── render.py           # (new) compose B&W outline + numbers; encode PNG/SVG
└── generation/             # AI TEXT-TO-IMAGE (network)
    ├── __init__.py
    ├── base.py             # (new) ImageProvider protocol + factory + AvailabilityError
    ├── openai_provider.py  # (new) default
    └── stability_provider.py # (new) optional
```

**Dependency direction:** `routers → {processing, generation, models, config}`.
`processing` depends on nothing but Pillow/OpenCV/NumPy (no FastAPI, no network)
so it is unit-testable in isolation (NFR5). `generation` depends only on the
provider SDKs + config.

---

## 3. Data Flow

### 3.1 Upload flow (US1 / FR1)

```
Browser                        FastAPI router            processing core
  │  multipart(file, complexity) │                          │
  ├─────────────────────────────►│ validate type+size (FR7) │
  │                              │ read bytes ─────────────►│ pipeline.run(bytes, complexity)
  │                              │                          │  downscale → quantize → regions
  │                              │                          │  → numbering → render(PNG/SVG)
  │                              │◄──── ColoringResult ──────┤  (legend[], page bytes)
  │◄── 200 JSON {page_image, legend, source_preview} ───────┤
```

### 3.2 Text flow (US2 / FR2)

```
Browser                  router               generation provider        processing core
  │ {prompt, complexity}   │                       │                         │
  ├───────────────────────►│ validate prompt (FR7) │                         │
  │                        │ provider.generate(prompt) ──► OpenAI/Stability   │
  │                        │◄──────── source PNG bytes ───┤ (502 on failure)  │
  │                        │ pipeline.run(source_bytes, complexity) ─────────►│
  │                        │◄──────────────── ColoringResult ─────────────────┤
  │◄ 200 {page_image, legend, source_preview=generated} ──┤
```

Both flows converge at `pipeline.run(raster_bytes, complexity)`. The **only**
difference is the source of `raster_bytes`. `source_preview` in the response is
the original upload (downscaled thumbnail) for US1, or the generated image for
US2 (design OQ4: show the source).

### 3.3 Lifecycle & cleanup (NFR2/A9)

- Request enters → bytes held in memory (and an optional temp file under a
  `tempfile.TemporaryDirectory()` if a library needs a path).
- Pipeline runs entirely in-process.
- Response serialized with inline data URLs (AD4).
- `TemporaryDirectory` context exits → all temp artifacts deleted before/at
  response return. **Nothing persists.**

---

## 4. API Contracts

All endpoints are mounted under `/api` (AD6). Content type `application/json`
unless noted. Errors use a consistent envelope.

### 4.1 `GET /api/health` (FR8)

`200 OK`
```json
{ "status": "ok", "version": "0.1.0", "text_flow_enabled": true }
```
- `text_flow_enabled` reflects whether a provider key is configured (drives the
  frontend's Describe-tab gating, FR11). Frontend calls this on load.
- **Compatibility:** `GET /health` (no prefix) remains as an alias returning
  `{"status":"ok"}` so the existing `test_health` passes (AD6, §11).

### 4.2 `POST /api/coloring/from-image` (FR1)

Request: `multipart/form-data`
- `file`: the image (JPG/PNG/WebP), required.
- `complexity`: `simple | medium | detailed` (default `medium`), optional form field.
- `output_format`: `png | svg` (default from `OUTPUT_FORMAT`), optional.

Success `200`:
```json
{
  "page_image": "data:image/png;base64,iVBORw0KGgo...",
  "format": "png",
  "width": 1275,
  "height": 1650,
  "legend": [
    { "n": 1, "name": "Red",      "hex": "#E11D48" },
    { "n": 2, "name": "Sky Blue", "hex": "#38BDF8" }
  ],
  "region_count": 12,
  "source_preview": "data:image/png;base64,..."
}
```

### 4.3 `POST /api/coloring/from-text` (FR2)

Request: `application/json`
```json
{ "prompt": "a friendly dinosaur", "complexity": "medium", "output_format": "png" }
```
Success `200`: **identical shape** to §4.2 (`source_preview` = generated image).

### 4.4 Error envelope (FR7, Edge Cases §8)

All non-2xx responses:
```json
{ "error": { "code": "FILE_TOO_LARGE", "message": "That file is 14 MB — the max is 10 MB." } }
```

| HTTP | `code` | When |
|------|--------|------|
| 400 | `UNSUPPORTED_TYPE` | Upload not JPG/PNG/WebP (FR7) |
| 400 | `FILE_TOO_LARGE` | Upload > `MAX_IMAGE_SIZE_MB` (FR7, NFR7) |
| 400 | `EMPTY_PROMPT` | Text flow with blank prompt (FR7) |
| 400 | `CONTENT_POLICY` | Provider rejected the prompt (Edge Cases) |
| 422 | `UNREADABLE_IMAGE` | Bytes can't be decoded by Pillow/OpenCV |
| 502 | `GENERATION_UNAVAILABLE` | Provider 5xx / timeout / rate-limit |
| 503 | `TEXT_FLOW_DISABLED` | `from-text` called with no provider key (FR11 safety net; UI normally hides this) |

Validation order for `from-image`: content-type → declared/streamed size →
decode. Size is enforced **before** fully buffering (stream-and-count, abort at
limit) to honor NFR7.

### 4.5 CORS (NFR3)

`CORSMiddleware` with `allow_origins = ALLOWED_ORIGINS.split(",")` (already wired
in `main.py`), methods limited to `GET, POST, OPTIONS`, no credentials.

---

## 5. Image Processing Pipeline (FR3)

The heart of the system. Input: source raster bytes + complexity. Output:
`ColoringResult { page_bytes, format, legend[], region_count, width, height }`.

```
                         ┌──────────────────────────────────────────────────┐
 raster bytes ──►(a)────►│ decode (Pillow) → RGB ndarray                     │
                         └──────────────────────────────────────────────────┘
        (b) downscale & normalize  ──► longest side ≤ PROC_MAX_PX (e.g. 1024) ; optional bilateral
                                        blur to flatten texture (smoothing ↑ for simpler levels)
        (c) color quantization     ──► OpenCV k-means to K clusters (K = palette size for level)
        (d) region labeling        ──► per quantized image: connected components → integer label map
        (e) clean regions          ──► remove/merge regions smaller than MIN_REGION_AREA into
                                        nearest neighbor (Edge Cases: tiny regions never crash)
        (f) outline extraction     ──► boundaries between labels → black 1–2px strokes on white
        (g) number placement       ──► for each region, compute a label anchor (distance-transform
                                        peak / pole-of-inaccessibility) and draw its palette index;
                                        skip label if region too small for legible text but keep region
        (h) palette mapping        ──► order clusters by luminance, map each to a named palette
                                        color (palette.py); build legend [{n,name,hex}]
        (i) render & encode        ──► PNG (default) or SVG; page sized to print aspect (§7)
```

### 5.1 Complexity presets (FR6 / A6)

| Level | K (colors/regions target) | Smoothing | Min region area |
|-------|---------------------------|-----------|-----------------|
| `simple` | 6 | high | larger (fewer, bigger regions) |
| `medium` (default) | 12 | medium | medium |
| `detailed` | 20 | low | smaller |

Values live in `config.py` and are env-tunable. **Region count is capped** by K +
the min-area merge step, which is the legibility guard for R2 and the DoS guard
for NFR7.

### 5.2 Numbering & legibility (R2, Edge Cases)

- Anchor = distance-transform maximum inside the region (keeps the number away
  from borders).
- Font size scales with region size, clamped to a min legible size.
- If even the min size won't fit, the region is left unlabeled but still outlined
  (PRD edge case: "never crash"). Its color still appears in the legend via its
  cluster.

### 5.3 Output rendering (FR4, R6)

- **Page aspect:** Letter (8.5×11) default, ~150 DPI target → e.g. 1275×1650 px
  (OQ2 default; configurable). Source image is fit/letterboxed into the page
  drawing area; the legend is rendered **into the same page** below the artwork so
  the downloaded PNG is self-contained and print-ready.
- **PNG** via Pillow. **SVG** (when `OUTPUT_FORMAT=svg`) emits region contours as
  `<path>` strokes + `<text>` numbers — scalable and crisp for print. SVG is the
  configured-only path; PNG is the always-on default to keep MVP risk low.

### 5.4 Testability (NFR5)

- Each pipeline stage is a pure function over ndarrays — unit-tested on a small
  fixture image (checked into `api/tests/fixtures/`) with **no network**.
- Determinism: k-means seeded with a fixed RNG so region counts/labels are
  stable across test runs.
- Degenerate inputs covered by tests: single-color image → ≥1 region, ≥1 legend
  entry (Edge Cases).

---

## 6. AI Generation Integration (FR2 / FR10 / FR11)

### 6.1 Provider interface (`generation/base.py`)

```python
class ImageProvider(Protocol):
    name: str
    def generate(self, prompt: str, size: int = 1024) -> bytes:  # PNG/JPEG bytes
        ...

class GenerationUnavailable(Exception): ...   # → 502
class ContentPolicyError(Exception): ...        # → 400 CONTENT_POLICY
```

`get_provider(settings) -> ImageProvider | None`
- Returns `OpenAIProvider` if `OPENAI_API_KEY` set (default).
- Else `StabilityProvider` if `STABILITY_API_KEY` set.
- Else `None` → text flow disabled (FR11). `from-text` then returns
  `503 TEXT_FLOW_DISABLED`; `/api/health` reports `text_flow_enabled=false`.

### 6.2 OpenAI provider (default, A2)

- Uses the `openai` SDK Images API; requests a **square 1024×1024** image
  (OQ3 default) then the pipeline fits it to page aspect.
- Maps provider errors: 429/5xx/timeout → `GenerationUnavailable` (502);
  content-policy rejection → `ContentPolicyError` (400, message surfaced to user).
- Timeout configured (e.g. 30s) so a hung provider can't pin a worker.

### 6.3 Stability provider (optional)

- httpx POST to Stability REST text-to-image; decode returned image bytes.
- Same error mapping. Selected only when OpenAI key absent and Stability key set.

### 6.4 Security of keys (NFR3 / R5)

- Keys read **only** server-side from env via `config.py`. Never serialized into
  any response, log line, or returned to the frontend. The frontend learns only
  the boolean `text_flow_enabled`.

---

## 7. Frontend Architecture

Single-screen SPA implementing design §1–§5. Component tree mirrors design §7:

```
App (holds UI-state reducer)
├── AppHeader
├── InputCard
│   ├── ModeTabs (Upload | Describe, describeEnabled from /api/health)
│   ├── Dropzone        (Upload mode; client-side type+size check, FR7/NFR3)
│   ├── PromptInput     (Describe mode)
│   ├── SourcePreview
│   ├── ComplexityPicker (default medium)
│   └── PrimaryCTA
└── ResultCard
    ├── LoadingSkeleton  (processing / generating states)
    ├── ColoringPage     (renders page_image data URL)
    ├── Legend           (entries[{n,name,hex}])
    ├── DownloadButton   (anchor download of data URL)
    ├── Banner/Toast     (error states)
    └── StartOver
```

- **UI state machine** (design §5) implemented as a `useReducer`:
  `idle → sourceReady → (generatingSource) → processing → result | error`.
- **On load:** `GET /api/health` → set `text_flow_enabled` to enable/disable the
  Describe tab (FR11, design §3 disabled variant).
- **Download:** the `page_image` data URL is set as an `<a download>` href — no
  extra request, consistent with stateless API (AD4).
- **Client validation first** (type/size) so obvious mistakes never hit the
  network; server re-validates (NFR3).

---

## 8. Deployment Strategy

### 8.1 Local (MVP target — NFR4)

- `./run.sh start` → `docker compose up -d` brings up `api` (:8000) and
  `frontend` (:3000). Single command, matches PRD G5 and the run.sh standard.
- `.env` copied from `.env.example`; `OPENAI_API_KEY` optional (upload flow works
  without it; text flow auto-disables — FR11).
- `./run.sh test` runs pytest in the api container (pipeline + provider-mock
  tests). `./run.sh logs|status|shell|clean|build` per the project standard.

### 8.2 Container specifics

- **api image:** python:3.11-slim base, `pip install -r requirements.txt`
  (opencv-python-**headless** avoids GUI/system GL deps; only minimal libs like
  libGL-free headless build needed). Runs `uvicorn app.main:app --host 0.0.0.0
  --port 8000`. Single worker for MVP (stateless, so scaling later = more
  replicas / workers with no shared state).
- **frontend image:** node base, `npm install`, `vite` dev server on :3000 with
  `VITE_API_URL=http://localhost:8000` (already set in compose). For a future
  prod build, `vite build` + static serve; out of MVP scope.
- Both services `restart: unless-stopped`; bind-mounts enable hot reload in dev.

### 8.3 Scaling & future (non-MVP, noted only)

Because the API is stateless (AD1), horizontal scaling is trivial later (N api
replicas behind a load balancer; no sticky sessions). A managed image store +
signed URLs would replace inline data URLs (AD4) if payload size becomes a
concern. These are explicitly **out of MVP scope**.

---

## 9. Cross-Cutting Concerns

| Concern | Approach | PRD ref |
|---------|----------|---------|
| Config | `config.py` reads env once into a typed settings object (size, format, palette sizes, smoothing, origins, provider keys, proc-max-px). | NFR3/NFR7 |
| Logging | Structured request logs (method, path, duration, outcome, region_count). **No PII / no image bytes / no keys** logged. | NFR6, R5 |
| Performance | Downscale before processing; cap proc resolution; seeded k-means; target <10s p95 for ≤10MB upload. | NFR1, R3 |
| Resource bounds | Max upload size, max proc pixels, max region count (via K + min-area merge). | NFR7 |
| Statelessness | TemporaryDirectory per request, deleted before response; no module-level mutable state → safe under concurrency. | NFR2, Edge Cases |
| Security | Keys server-only; CORS restricted; size/type validation; SVG output sanitized (numbers/paths only, no external refs). | NFR3, R5 |

---

## 10. Key Trade-offs (explicit)

1. **Inline data URLs vs. file store (AD4).** Chosen: inline. Pro: zero storage,
   true statelessness, one round-trip, simplest MVP. Con: larger JSON payloads
   (a ~1275×1650 PNG base64 ≈ a few hundred KB to low MB). Acceptable for a
   single-page, single-user local app; revisit if payloads grow.
2. **Fixed palette vs. source-color extraction (AD5).** Chosen: fixed named
   palette. Pro: human-readable legend, simple, deterministic. Con: legend colors
   don't match the photo. Documented as a fast-follow (PRD A4).
3. **PNG-first, SVG-optional (§5.3).** Chosen: PNG always on, SVG behind config.
   Pro: lowers MVP risk (raster path is straightforward). Con: SVG path is less
   exercised; gated by `OUTPUT_FORMAT`.
4. **K-means quantization vs. edge-detection-first (per CLAUDE.md flow note).**
   The CLAUDE.md sketch mentions "edge detection → simplification." We choose
   **quantization-driven region segmentation** because color-by-number needs
   *closed colored regions with assigned numbers*, which falls out naturally from
   quantize→label→contour. Pure edge detection yields open contours that are hard
   to fill/number reliably. Outlines are still derived (step f) for the B&W page.

---

## 11. Impact on Existing Scaffold & Open Items

- **Health route (AD6):** add `/api/health` (rich payload) and keep `/health`
  alias so `api/tests/test_health.py` keeps passing. Coding phase must not break
  the existing test.
- **New modules:** all files listed in §2 are new; `processing/__init__.py` and
  `generation/__init__.py` already exist (empty) and will be populated.
- **No new dependencies:** `requirements.txt` and `package.json` already contain
  everything needed.
- **Test fixtures:** coding phase should add a tiny sample image under
  `api/tests/fixtures/` to enable network-free pipeline tests (NFR5).
- **SVG depth:** MVP ships PNG fully; SVG is best-effort behind `OUTPUT_FORMAT`
  and may be marked minimal if time-boxed (does not block the MVP acceptance
  criteria, which require PNG download).

---

## 12. Mapping Architecture → PRD Requirements

| PRD item | Where addressed |
|----------|-----------------|
| FR1 from-image | §4.2, §3.1, §5 |
| FR2 from-text | §4.3, §3.2, §6 |
| FR3 pipeline | §5 (a–i) |
| FR4 output formats / print size | §5.3, §4.2 |
| FR5 legend | §5 (h), §4.2 |
| FR6 complexity presets | §5.1 |
| FR7 validation | §4.4 |
| FR8 health | §4.1 |
| FR9 two modes | §7 |
| FR10 provider abstraction | §6.1 |
| FR11 graceful degradation | §6.1, §4.4 (503), §7 |
| NFR1 performance | §5, §9 |
| NFR2 statelessness | §3.3, §9 |
| NFR3 security | §4.5, §6.4, §9 |
| NFR4 portability | §8.1 |
| NFR5 testability | §5.4, §2 |
| NFR6 observability | §9 |
| NFR7 resource bounds | §5.1, §9, AD7 |
| Edge cases §8 | §4.4, §5.2 |
| Risks R1–R7 | §6, §5.1/§5.2, §5.3, §6.4, §10 |
