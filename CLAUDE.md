# CLAUDE.md

## Project
coloring-book — Generates coloring pages from an uploaded image or text prompt. Converts to a B&W numbered silhouette for color-by-number. Supports both image upload and text-to-image generation.

## Tech Stack
- **Backend:** Python (FastAPI) — image processing (OpenCV, Pillow), AI image generation
- **Frontend:** React — file upload, text prompt input, coloring page viewer
- **Infra:** Docker Compose

## Key Flows
1. **Image upload** → edge detection → simplification → region segmentation → number assignment → SVG/PNG output
2. **Text prompt** → AI image generation (e.g. DALL-E / Stable Diffusion) → same pipeline as above

## Local Setup
```bash
cp .env.example .env   # fill in OPENAI_API_KEY or equivalent
./run.sh start
# API: http://localhost:8000
# Frontend: http://localhost:3000
```

## Key Commands
- `./run.sh start` — start all services
- `./run.sh test`  — run tests
- `./run.sh logs`  — tail logs
- `./run.sh shell` — shell into api container

## Rules
- Keep changes minimal and focused
- Run tests before committing
- Image processing logic lives in `api/app/processing/`
- AI generation logic lives in `api/app/generation/`
