# PRD — coloring-book

**Status:** Draft (iteration 1)
**Author:** Systems Analyst (PM pipeline)
**Date:** 2026-05-24

---

## 1. Problem Statement

Parents, teachers, and hobbyists want personalized color-by-number coloring
pages but have no easy way to make them. Existing coloring books are
fixed-content and generic; turning a favorite photo or an idea ("a cat on a
roof") into a clean, numbered, color-by-number outline today requires manual
work in image-editing software and design skill most people don't have.

**coloring-book** solves this: a user supplies either an image or a text
description, and the app produces a printable black-and-white outline divided
into numbered regions, with a legend mapping each number to a suggested color.

The pain is felt most by:
- **Parents** wanting a custom activity for a child (e.g. a photo of the family pet).
- **Teachers** producing themed classroom worksheets quickly.
- **Casual creators** who want a fun, shareable artifact from a photo or idea.

---

## 2. Goals

| # | Goal | Success Measure (MVP) |
|---|------|------------------------|
| G1 | Convert an uploaded image into a numbered color-by-number page | A user can upload a JPG/PNG and download a B&W numbered outline + color legend |
| G2 | Generate a coloring page from a text prompt | A user can type a prompt, the app generates an image via an AI provider, then runs the same pipeline |
| G3 | Output is printable | Output renders cleanly on a single A4/Letter page as PNG (and SVG when configured) |
| G4 | Fast enough to feel interactive | Image-upload flow completes in < 10 s p95; text flow bounded by provider latency + < 10 s processing |
| G5 | Runs locally with one command | `./run.sh start` brings up API + frontend via Docker Compose |

**Primary success criterion for MVP:** both input paths (upload, text) produce a
downloadable numbered coloring page with a color legend, verifiable end-to-end
in the browser.

---

## 3. Non-Goals (MVP)

- **No user accounts / auth / persistence of user libraries.** Pages are
  generated, downloaded, and discarded. No login.
- **No payment / billing / quotas per user.**
- **No mobile-native app.** Responsive web only.
- **No collaborative editing or sharing links.**
- **No print-shop integration / physical shipping.**
- **No in-browser coloring tool.** We produce the *printable* numbered outline;
  actual coloring happens on paper (or any external app). A digital coloring
  canvas is a future phase.
- **No fine-tuned/self-hosted diffusion model.** Text-to-image uses a hosted
  provider API (OpenAI by default, Stability optional).
- **No advanced palette theory** (no per-region color extraction from the
  source photo in MVP — see Assumptions A4). A fixed N-color palette is assigned.

---

## 4. Users & Personas

- **Priya, the parent (primary):** Non-technical. Uploads a phone photo of the
  family dog. Wants a printable page in under a minute, no jargon.
- **Mr. Lewis, the teacher:** Slightly more patient. Types prompts like
  "a friendly dinosaur" to make themed worksheets. Cares that output prints on
  one page.
- **Sam, the hobbyist:** Experiments with prompts and complexity settings to get
  a pleasing level of detail.

Mental model for all: *"Give it a picture or an idea → get a coloring page."*
The numbered regions and color legend must be self-explanatory.

---

## 5. User Stories

**US1 — Upload an image**
> As a parent, I upload a photo of my dog, choose a complexity level, and
> download a black-and-white numbered outline with a color legend, so my child
> can color it in.

Acceptance:
- Accept JPG, PNG, WebP up to `MAX_IMAGE_SIZE_MB` (default 10 MB).
- Show a preview of the uploaded image before processing.
- After processing, show the generated coloring page with a download button.

**US2 — Generate from a text prompt**
> As a teacher, I type "a friendly dinosaur", the app generates an image, and
> produces the same kind of numbered coloring page.

Acceptance:
- A text input + "Generate" button.
- Generated source image is shown, then the coloring page.
- If the AI provider key is missing/invalid, show a clear error and fall back
  gracefully (text flow disabled with explanatory message; upload flow still works).

**US3 — Choose complexity**
> As a hobbyist, I pick "Simple / Medium / Detailed" to control how many regions
> and how much detail the outline has.

Acceptance:
- Three preset complexity levels mapping to internal parameters
  (number of color regions / smoothing). See Requirement FR6.

**US4 — Download the page**
> As any user, I download the result as a PNG (default) sized for A4/Letter,
> including the numbered outline and the color legend.

Acceptance:
- One-click download of the rendered page.
- Legend (number → color name/swatch) is part of, or adjacent to, the output.

**US5 — See progress / errors**
> As any user, I see a loading state while processing and a clear message if
> something fails (bad file, oversized file, generation failure, processing
> failure).

---

## 6. Functional Requirements

| ID | Requirement |
|----|-------------|
| FR1 | **Image upload endpoint.** `POST /api/coloring/from-image` accepts multipart image + `complexity` param; returns the generated page (and legend). |
| FR2 | **Text generation endpoint.** `POST /api/coloring/from-text` accepts `{ prompt, complexity }`; calls the AI provider to generate a source image, then runs the pipeline; returns page + legend. |
| FR3 | **Processing pipeline.** Given a source raster image, produce a color-by-number page: (a) downscale/normalize, (b) reduce to N color regions via color quantization, (c) derive region boundaries/outline, (d) place a number label in each region, (e) emit a B&W outline with numbers + a legend mapping number → palette color. |
| FR4 | **Output formats.** PNG by default; SVG when `OUTPUT_FORMAT=svg`. Output dimensioned for single-page print (A4/Letter aspect, ~150 DPI target). |
| FR5 | **Color legend.** Each region number maps to a named palette color (e.g. `1 = Red`, `2 = Sky Blue`). Legend returned alongside/within the image. |
| FR6 | **Complexity presets.** `simple` ≈ 6 colors, `medium` ≈ 12 colors, `detailed` ≈ 20 colors (exact counts tunable in config). Higher complexity = more regions, less smoothing. |
| FR7 | **Validation.** Reject unsupported types and oversized files with HTTP 400 and a clear message. Reject empty prompts. |
| FR8 | **Health & readiness.** `GET /api/health` returns service status (already scaffolded as `test_health`). |
| FR9 | **Frontend flows.** Two tabs/modes: "Upload" and "Describe". Each shows source preview → loading → result with download. |
| FR10 | **Provider abstraction.** AI generation behind an interface so OpenAI (default) or Stability can be selected by config/env without frontend changes. |
| FR11 | **Graceful degradation.** If no AI key configured, the text flow is disabled in the UI with a tooltip/message; the upload flow remains fully functional. |

---

## 7. Non-Functional Requirements

| ID | Requirement |
|----|-------------|
| NFR1 | **Performance.** Image-upload processing < 10 s at p95 for inputs ≤ 10 MB on a typical laptop/container. |
| NFR2 | **Statelessness.** API holds no user state; processing is request-scoped. Temp files cleaned up after response. |
| NFR3 | **Security.** No secrets in code or client. API key only server-side via env. Validate/limit upload size and type to prevent abuse. CORS limited to `ALLOWED_ORIGINS`. |
| NFR4 | **Portability.** Runs via Docker Compose on Linux/macOS with one command. No external services beyond the AI provider (only needed for text flow). |
| NFR5 | **Testability.** Pipeline functions unit-testable on a fixed sample image without network. AI provider mockable in tests. |
| NFR6 | **Observability.** Structured request logs; errors logged with enough context to debug (no PII beyond the transient image). |
| NFR7 | **Resource bounds.** Cap output resolution and region count to avoid CPU/memory blowups (DoS guardrail). |

---

## 8. Edge Cases

- **Oversized / wrong-type upload** → 400 with message; UI surfaces it.
- **Corrupt / unreadable image** → 422, "Could not read image."
- **Very low-detail source** (e.g. a blank or single-color image) → still
  produces at least 1 region; legend has ≥ 1 entry; no crash.
- **Very high-detail source** (busy photo) → region count capped by complexity
  preset; output remains legible (numbers don't overlap into illegibility — see Risk R2).
- **AI provider down / rate-limited / 5xx** → return 502 with "Generation
  service unavailable, try again"; UI shows retry.
- **Missing/invalid AI key** → text flow disabled (FR11); no 500s.
- **Empty or abusive prompt** (empty, or policy-violating) → 400 for empty;
  surface provider content-policy rejections as a clear user message.
- **Tiny regions** where a number won't fit → merge into neighbor or skip the
  label but keep the region; never crash.
- **Concurrent requests** → each request independent; no shared mutable state.

---

## 9. Dependencies

- **AI image provider:** OpenAI Images API (default) via `OPENAI_API_KEY`;
  Stability AI optional via `STABILITY_API_KEY`. Required only for the text flow.
- **Image-processing libraries:** Pillow + OpenCV + NumPy (color quantization,
  contours, labeling). scikit-image optional if needed.
- **Frontend:** React + Vite.
- **Infra:** Docker, Docker Compose. `run.sh` wrapper (project standard).
- **No database** in MVP.

---

## 10. Risks & Mitigations

| ID | Risk | Likelihood | Impact | Mitigation |
|----|------|-----------|--------|------------|
| R1 | AI provider cost/latency/availability hurts text flow | Med | Med | Provider abstraction (FR10); upload flow independent; clear errors + retry (FR11) |
| R2 | Numbered regions become illegible on busy images | Med | High | Complexity presets cap region count (FR6); smoothing; merge tiny regions; legible default = `medium` |
| R3 | Processing too slow for large images | Med | Med | Downscale before processing; cap output resolution (NFR7); enforce size limit (FR7) |
| R4 | Provider content-policy rejects a prompt | Low | Low | Surface provider message verbatim-ish to user; don't crash |
| R5 | Secrets leak to client | Low | High | Keys server-side only; never returned to frontend (NFR3) |
| R6 | Output doesn't fit one printed page | Med | Med | Fixed A4/Letter aspect + DPI target (FR4); verify in QA |
| R7 | Scope creep into a full digital coloring tool | Med | Med | Explicit non-goal (§3); MVP produces printable output only |

---

## 11. Assumptions

- **A1** — Single-user, local-first MVP. No auth, no accounts, no persistence
  (decision; aligns with "MVP" + project scaffolding having no DB).
- **A2** — OpenAI is the default text-to-image provider because `OPENAI_API_KEY`
  is the primary key in `.env.example`. Stability is an optional alternative.
- **A3** — "Numbered silhouette" = a black outline divided into closed regions,
  each labeled with a number; plus a legend mapping numbers to suggested colors.
  We do **not** require the suggested colors to match the original photo's
  colors in MVP (see A4).
- **A4** — MVP assigns colors from a **fixed named palette** (sized to the
  complexity level) rather than extracting true colors from the source image.
  This keeps the pipeline simple and the legend human-readable. Source-color
  matching is a fast-follow enhancement.
- **A5** — Output target is single-page A4/Letter, PNG by default, ~150 DPI.
- **A6** — Complexity presets: `simple`=6, `medium`=12 (default), `detailed`=20
  colors/regions; tunable via config.
- **A7** — Supported uploads: JPG, PNG, WebP; max 10 MB (from `MAX_IMAGE_SIZE_MB`).
- **A8** — Frontend served at :3000, API at :8000, per existing scaffolding.
- **A9** — Generated/temp images are transient and deleted after the response;
  nothing is stored long-term.

---

## 12. Open Questions

> Resolved with default decisions for MVP per PM directive (no blocking on answers).

- **OQ1** — Should the legend's color *names* be standardized (e.g. Crayola-like
  set) or generic ("Color 1…N")? **Default:** use a small set of common named
  colors (Red, Orange, Yellow, Green, Blue, Purple, Brown, Black, Pink, Gray, …)
  sized to the palette; fall back to "Color N" beyond the named set.
- **OQ2** — Print sizing: A4 vs Letter default? **Default:** Letter aspect,
  but keep output square-ish and printable on both; make it configurable later.
- **OQ3** — Should text-flow source images be square (1024×1024) and then
  letterboxed, or matched to page aspect? **Default:** request square from the
  provider, then fit to page during rendering.
- **OQ4** — Do we expose the raw generated source image to the user, or only the
  coloring page? **Default:** show the source preview (helps US2 trust), but the
  downloadable artifact is the coloring page.

---

## 13. Acceptance Criteria (MVP "Done")

The MVP is complete when **all** of the following are verifiable in the browser
and by automated tests:

1. **Upload flow:** Upload a JPG/PNG ≤ 10 MB, pick a complexity, and download a
   B&W numbered coloring page with a color legend. (US1, US4)
2. **Text flow:** Enter a prompt with a valid provider key, see the generated
   source preview, and download the resulting numbered coloring page. (US2, US4)
3. **Complexity:** Switching `simple/medium/detailed` visibly changes region
   count. (US3)
4. **Errors:** Oversized/wrong-type upload, empty prompt, and provider failure
   each show a clear, non-crashing error. Missing key disables text flow only. (US5, FR7, FR11)
5. **Health:** `GET /api/health` returns OK; `./run.sh test` passes.
6. **Run:** `./run.sh start` brings up both services; `./run.sh help` lists the
   standard commands.
7. **Security:** No keys in client or repo; uploads size/type-validated; CORS
   restricted to configured origins.
