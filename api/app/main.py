from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import settings
from .routers import coloring

app = FastAPI(title="coloring-book API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(coloring.router)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Render HTTPExceptions in the standard error envelope (architecture §4.4).

    If ``detail`` is already a {code, message} dict we pass it through; otherwise
    we wrap the plain detail string under a generic code.
    """
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
