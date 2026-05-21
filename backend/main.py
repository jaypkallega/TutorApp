import socket
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: create tables and seed default settings."""
    # Import all models BEFORE create_all so metadata is populated
    import backend.models  # noqa: F401
    from backend.database import engine, Base
    Base.metadata.create_all(bind=engine)
    _seed_default_settings()
    # Seed misconceptions database
    from backend.processing.misconception_matcher import seed_misconceptions
    from backend.database import SessionLocal
    _seed_db = SessionLocal()
    try:
        seed_misconceptions(_seed_db)
    finally:
        _seed_db.close()
    logger.info("MathTutor started — tables ready.")
    yield
    logger.info("MathTutor shutting down.")


def _seed_default_settings():
    from backend.database import SessionLocal
    from backend.models.settings import AppSetting
    from backend.config import (
        DEFAULT_LLM_PROVIDER, DEFAULT_LLM_API_KEY, DEFAULT_LLM_MODEL,
        DEFAULT_LLM_BASE_URL, DEFAULT_OCR_MODE, LAN_ONLY_MODE,
    )

    db = SessionLocal()
    defaults = [
        ("llm_provider",   DEFAULT_LLM_PROVIDER,  "LLM Provider: openai/anthropic/gemini/custom"),
        ("llm_api_key",    DEFAULT_LLM_API_KEY,    "Your LLM API Key"),
        ("llm_model_name", DEFAULT_LLM_MODEL,      "Model name to use"),
        ("llm_base_url",   DEFAULT_LLM_BASE_URL,   "Custom base URL (leave blank for default)"),
        ("ocr_mode",       DEFAULT_OCR_MODE,       "OCR mode: local/vision_api/hybrid"),
        ("lan_only_mode",  LAN_ONLY_MODE,          "Restrict access to LAN only (1/0)"),
        ("app_version",    "1.0.0",                "Application version"),
    ]
    for key, value, desc in defaults:
        existing = db.query(AppSetting).filter(AppSetting.key == key).first()
        if not existing:
            db.add(AppSetting(key=key, value=value, description=desc))
    db.commit()
    db.close()


app = FastAPI(
    title="MathTutor API",
    description="Local home-network math learning app for Grade 8",
    version="1.0.0",
    lifespan=lifespan,
)

# ── LAN-only middleware ─────────────────────────────────────────────────────

PRIVATE_PREFIXES = ("10.", "172.", "192.168.", "127.", "::1")


@app.middleware("http")
async def lan_only_middleware(request: Request, call_next):
    # Always allow API docs and health check during setup
    if request.url.path in ("/api/health", "/docs", "/openapi.json", "/redoc"):
        return await call_next(request)

    from backend.database import SessionLocal
    from backend.models.settings import AppSetting
    db = SessionLocal()
    try:
        setting = db.query(AppSetting).filter(AppSetting.key == "lan_only_mode").first()
        lan_only = setting.value == "1" if setting else True
    finally:
        db.close()

    if lan_only:
        client_ip = request.client.host if request.client else "127.0.0.1"
        if not any(client_ip.startswith(p) for p in PRIVATE_PREFIXES):
            return JSONResponse(
                status_code=403,
                content={"detail": "Access restricted to home network only."},
            )
    return await call_next(request)


# ── CORS ────────────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── API Routers ─────────────────────────────────────────────────────────────

from backend.api.v1 import auth, settings as settings_router
from backend.api.v1 import textbooks, chapters, exercises, assignments, submissions, evaluations, misconceptions, teach, submission_drafts

app.include_router(auth.router,         prefix="/api/v1/auth",        tags=["Auth"])
app.include_router(settings_router.router, prefix="/api/v1/settings", tags=["Settings"])
app.include_router(textbooks.router,    prefix="/api/v1/textbooks",   tags=["Textbooks"])
app.include_router(chapters.router,     prefix="/api/v1/chapters",    tags=["Chapters"])
app.include_router(exercises.router,    prefix="/api/v1/exercises",   tags=["Exercises"])
app.include_router(assignments.router,  prefix="/api/v1/assignments", tags=["Assignments"])
app.include_router(submissions.router,  prefix="/api/v1/submissions", tags=["Submissions"])
app.include_router(evaluations.router,  prefix="/api/v1/evaluations", tags=["Evaluations"])
app.include_router(misconceptions.router, prefix="/api/v1/misconceptions", tags=["Misconceptions"])
app.include_router(teach.router,         prefix="/api/v1/teach",         tags=["Teaching"])
app.include_router(submission_drafts.router, prefix="/api/v1/drafts",       tags=["Drafts"])

# ── Static frontend ─────────────────────────────────────────────────────────

from backend.config import BASE_DIR

frontend_build = BASE_DIR / "frontend" / "dist"
if frontend_build.exists():
    app.mount("/", StaticFiles(directory=str(frontend_build), html=True), name="static")

# ── Health check ─────────────────────────────────────────────────────────────

@app.get("/api/health", tags=["Health"])
def health_check():
    hostname = socket.gethostname()
    try:
        local_ip = socket.gethostbyname(hostname)
    except Exception:
        local_ip = "127.0.0.1"
    return {
        "status": "ok",
        "app": "MathTutor",
        "version": "1.0.0",
        "local_ip": local_ip,
        "docs": "http://localhost:8000/docs",
    }
