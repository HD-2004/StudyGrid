"""StudyGrid application entry point.

Run: .venv\\Scripts\\python.exe -m uvicorn app.main:app --reload
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.routes import router

app = FastAPI(
    title="StudyGrid",
    description="AI study and review planner with adaptive spaced repetition.",
    version="0.1.0",
)

# The Vite dev server runs on a different origin, so the browser needs CORS to
# reach this API. Scoped to localhost dev ports.
#
# NOTE: this API has no authentication. Acceptable for a single-user local demo,
# but any plan is readable by anyone who can reach the port. Do not deploy as-is
# to a public host without adding auth.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

app.include_router(router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
