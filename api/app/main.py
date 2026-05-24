from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from . import db
from .config import settings
from .routers import coloring


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: connect to DB if configured
    if settings.database_url:
        try:
            db.init(settings.database_url)
        except Exception as exc:
            # Non-fatal: app works without DB, library features are just disabled
            print(f"[coloring-book] DB init failed (library disabled): {exc}")
    yield
    # Shutdown: nothing to clean up (psycopg2 pool GC'd naturally)


app = FastAPI(title="coloring-book API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(coloring.router)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Render HTTPExceptions in the standard error envelope (architecture §4.4)."""
    detail = exc.detail
    if isinstance(detail, dict) and "code" in detail and "message" in detail:
        body = {"error": detail}
    else:
        body = {"error": {"code": "ERROR", "message": str(detail)}}
    return JSONResponse(status_code=exc.status_code, content=body)


@app.get("/health")
def health():
    """Backward-compatible health alias (AD6); rich payload lives at /api/health."""
    return {"status": "ok"}
