# coloring-book

Generates coloring pages from an uploaded image or text prompt — converts to a B&W numbered silhouette for color-by-number.

## How it works

1. **Upload an image** (photo, drawing, anything) — or —
2. **Describe what you want** ("Superman flying", "a cat on a roof")
3. The app generates a clean black & white outline divided into numbered sections
4. Each number maps to a suggested color — the child colors by number

## Quick Start

```bash
cp .env.example .env   # add your API keys
./run.sh start
```

Open http://localhost:3000

See `./run.sh help` for all commands.

## Development

| Command | Description |
|---------|-------------|
| `./run.sh start` | Start all services |
| `./run.sh stop` | Stop all services |
| `./run.sh logs [svc]` | Tail logs |
| `./run.sh build` | Rebuild images |
| `./run.sh test` | Run test suite |
| `./run.sh shell [svc]` | Open shell (default: api) |
| `./run.sh clean` | Stop and remove volumes |

## Services

| Service | Port | Description |
|---------|------|-------------|
| `api` | 8000 | Python FastAPI — image processing + AI generation |
| `frontend` | 3000 | React — upload UI and coloring page viewer |
