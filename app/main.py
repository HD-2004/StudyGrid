"""StudyGrid application entry point.

Run: .venv\\Scripts\\python.exe -m uvicorn app.main:app --reload
"""

import os
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .api.routes import router
from .security import AnonymousSessionMiddleware

app = FastAPI(
    title="StudyGrid",
    description="AI study and review planner with adaptive spaced repetition.",
    version="0.1.0",
)

# The Vite dev server runs on a different origin, so the browser needs CORS to
# reach this API. Scoped to localhost dev ports.
#
# Anonymous sessions are isolated by a signed HttpOnly cookie. CORS credentials
# are therefore allowed only for the explicit origin allowlist below.
configured_origins = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "").split(",")
    if origin.strip()
]
dev_origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=configured_origins or dev_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type"],
)

app.add_middleware(AnonymousSessionMiddleware)

app.include_router(router)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    """Apply a conservative browser baseline to API and hosted frontend responses."""
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "same-origin")
    response.headers.setdefault(
        "Permissions-Policy", "camera=(), microphone=(), geolocation=()"
    )
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; font-src 'self'; connect-src 'self'; "
        "frame-ancestors 'none'; base-uri 'self'; form-action 'self'",
    )
    if request.url.path.startswith("/api/"):
        response.headers.setdefault("Cache-Control", "no-store")
    return response


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "api_version": "2026-09-health-1"}


# A production container copies the Vite build here. Mounting it after API and
# health routes keeps the application single-origin without affecting local
# development, where the directory is normally absent or served by Vite.
web_dist = Path(__file__).resolve().parent.parent / "web" / "dist"
if web_dist.is_dir():
    app.mount("/", StaticFiles(directory=web_dist, html=True), name="web")
