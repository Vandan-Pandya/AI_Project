"""
EduMentor AI — Minimal Core Backend (9 Essential Endpoints).
PostgreSQL Database, JWT Authentication, and AI Exam Evaluation.
Interactive Swagger API documentation available at http://127.0.0.1:8000/docs
"""

from __future__ import annotations
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from app.core import config
from app.core.database import init_db
from app.schemas.schemas import HealthResponse
from app.api import routes_auth, routes_chat, routes_exams

# ---------------------------------------------------------------------------
# FastAPI App Initialization
# ---------------------------------------------------------------------------
app = FastAPI(
    title="EduMentor AI Backend (Core MVP)",
    description="Minimal, high-impact educational AI backend: JWT Auth, EduMentor Study Chat, and AI Exam Evaluation.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    """Initializes PostgreSQL tables on startup."""
    try:
        init_db()
        print("[EduMentor] Database tables initialized successfully.")
    except Exception as e:
        print(f"[EduMentor] Database notice: {e}")


# ---------------------------------------------------------------------------
# Core Endpoints: System & Routers
# ---------------------------------------------------------------------------
@app.get("/", include_in_schema=False)
@app.get("", include_in_schema=False)
def root():
    """Redirects to Swagger interactive documentation."""
    return RedirectResponse(url="/docs")


@app.get("/health", response_model=HealthResponse, tags=["System"], summary="9. Server health check")
def health() -> HealthResponse:
    """Returns server and AI provider operational status."""
    has_key = bool(config.GEMINI_API_KEY or config.AI_API_KEY)
    return HealthResponse(
        status="ok",
        provider=config.get_active_provider(),
        model=config.get_active_model(),
        mode="live" if has_key else "mock"
    )


# Mount Core Feature Routers
app.include_router(routes_auth.router)
app.include_router(routes_chat.router)
app.include_router(routes_exams.router)
