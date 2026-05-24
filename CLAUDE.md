# CLAUDE.md

## Project
coloring-book — Generates coloring pages from an uploaded image or text prompt. Converts to a B&W numbered silhouette for color-by-number. Supports both image upload and text-to-image generation.

## Tech Stack
- **Backend:** Python (FastAPI) — image processing (OpenCV, Pillow), AI image generation
- **Frontend:** React — file upload, text prompt input, coloring page viewer
- **Infra:** Docker Compose

## Key Flows
1. **Inspire (upload)** → GPT-4o Vision describes → DALL-E 3 regenerates as coloring-book art → pipeline → save to library
2. **Describe (text)** → DALL-E 3 generates → pipeline → save to library
3. **Browse** → paginated gallery from PostgreSQL, filterable by auto-detected category

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
- DB logic lives in `api/app/db.py`; category detection in `api/app/categorizer.py`
