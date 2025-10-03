"""
COM-AI v3 - George's Brain Multi-Provider Orchestrator
Main entry point for the brain-enabled API server
"""

from __future__ import annotations

import os
import logging
from contextlib import asynccontextmanager
from typing import Any, Dict, List

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from src.utils.config import get_settings
from src.utils.logging_config import setup_logging

# DB lifecycle + health
from src.api.db.session import init_db_engine, dispose_db_engine, check_db_connection

# Provider Manager (new architecture; uses auto_adapter internally)
from src.api.brain.providers.manager import ProviderManager

# Provider wrappers
from src.brain.providers.openai_provider import OpenAIProvider
from src.brain.providers.anthropic_provider import AnthropicProvider
from src.brain.providers.gemini_provider import GeminiProvider

# API routes
from src.api.routes.brain import router as brain_router
from src.api.routes.providers import router as providers_router

# Health check routes (NEW)
from src.api.health.db import router as db_health_router
from src.api.health.firebase import router as firebase_health_router
from src.api.health.usage import router as usage_health_router

# --- Load env & logging early ---
load_dotenv()
setup_logging()
logger = logging.getLogger(__name__)

settings = get_settings()

brain_available = False


# ------------------------------------------------------------------------------
# Provider wiring helpers
# ------------------------------------------------------------------------------

def _bool_env(name: str, default: bool = False) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    return str(v).strip().lower() in {"1", "true", "yes", "on", "y"}


def _get_env_or_settings(key_env: str, key_settings: str, default: str | None = None) -> str | None:
    val = os.getenv(key_env)
    if val:
        return val
    return getattr(settings, key_settings, default)


def build_providers() -> Dict[str, Any]:
    """
    Instantiate provider wrappers if API keys are present.
    Missing keys are logged and that provider is skipped (app still boots).
    """
    providers: Dict[str, Any] = {}

    # --- OpenAI ---
    openai_key = _get_env_or_settings("OPENAI_API_KEY", "openai_api_key")
    openai_model = _get_env_or_settings("OPENAI_MODEL", "openai_model", "gpt-4o-mini")
    if openai_key:
        try:
            providers["openai"] = OpenAIProvider(api_key=openai_key, model=openai_model)
            logger.info("Provider 'openai' registered (model=%s)", openai_model)
        except Exception as e:
            logger.exception("Failed to initialize OpenAIProvider: %s", e)
    else:
        logger.warning("OPENAI_API_KEY missing; 'openai' provider disabled")

    # --- Anthropic ---
    anth_key = _get_env_or_settings("ANTHROPIC_API_KEY", "anthropic_api_key")
    anth_model = _get_env_or_settings("ANTHROPIC_MODEL", "anthropic_model", "claude-opus-4-1-20250805")
    if anth_key:
        try:
            providers["anthropic"] = AnthropicProvider(api_key=anth_key, model=anth_model)
            logger.info("Provider 'anthropic' registered (model=%s)", anth_model)
        except Exception as e:
            logger.exception("Failed to initialize AnthropicProvider: %s", e)
    else:
        logger.warning("ANTHROPIC_API_KEY missing; 'anthropic' provider disabled")

    # --- Gemini ---
    gem_key = _get_env_or_settings("GEMINI_API_KEY", "gemini_api_key")
    gem_model = _get_env_or_settings("GEMINI_MODEL", "gemini_model", "gemini-1.5-flash")
    if gem_key:
        try:
            providers["gemini"] = GeminiProvider(api_key=gem_key, model=gem_model)
            logger.info("Provider 'gemini' registered (model=%s)", gem_model)
        except Exception as e:
            logger.exception("Failed to initialize GeminiProvider: %s", e)
    else:
        logger.warning("GEMINI_API_KEY missing; 'gemini' provider disabled")

    if not providers:
        logger.error("No providers registered. The API will start, but synthesis calls will 503/500.")

    return providers


def _build_firebase_config() -> Dict[str, str | None]:
    """
    Collect Firebase client config + Admin credentials into app.state.firebase.
    NOTE: Web API key is *not* secret (frontend uses it), but we still avoid logging it.
    """
    cfg = {
        "apiKey": _get_env_or_settings("FIREBASE_API_KEY", "firebase_api_key"),
        "authDomain": _get_env_or_settings("FIREBASE_AUTH_DOMAIN", "firebase_auth_domain"),
        "projectId": _get_env_or_settings("FIREBASE_PROJECT_ID", "firebase_project_id"),
        "storageBucket": _get_env_or_settings("FIREBASE_STORAGE_BUCKET", "firebase_storage_bucket"),
        "messagingSenderId": _get_env_or_settings("FIREBASE_MESSAGING_SENDER_ID", "firebase_messaging_sender_id"),
        "appId": _get_env_or_settings("FIREBASE_APP_ID", "firebase_app_id"),
        "measurementId": _get_env_or_settings("FIREBASE_MEASUREMENT_ID", "firebase_measurement_id"),
        # Admin SDK credentials file path (backend)
        "adminCredentials": _get_env_or_settings("GOOGLE_APPLICATION_CREDENTIALS", "google_application_credentials"),
    }
    return cfg


def _redact(s: str | None, left: int = 6, right: int = 2) -> str | None:
    if not s:
        return None
    if len(s) <= left + right:
        return "*" * len(s)
    return f"{s[:left]}…{s[-right:]}"


# ------------------------------------------------------------------------------
# Lifespan (startup/shutdown)
# ------------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Handles startup and shutdown for database and providers.
    """
    global brain_available

    # ===== STARTUP =====
    logger.info("🚀 Application startup initiated")

    # Initialize database engine (respects .env knobs via session.py)
    try:
        logger.info("🗄️  Initializing database engine...")
        init_db_engine()  # override for verbose dev: init_db_engine(echo=True)
        logger.info("✅ Database engine initialized")
    except Exception as e:
        logger.exception("❌ Database initialization failed: %s", e)
        logger.warning("⚠️  Continuing without database (degraded mode)")

    # Build providers + ProviderManager (uses auto_adapter internally)
    try:
        providers_dict: Dict[str, Any] = build_providers()
        # ✅ Attach manager to app.state (routes will use this)
        app.state.provider_manager = ProviderManager(providers_dict)
        total_registered = len(providers_dict)
        logger.info(
            "✅ ProviderManager initialized with providers=%s (total=%d)",
            list(providers_dict.keys()), total_registered
        )
        brain_available = total_registered > 0
    except Exception as e:
        logger.exception("⚠️  ProviderManager setup failed: %s", e)
        app.state.provider_manager = None
        brain_available = False

    # Attach Firebase config to app.state and log presence
    try:
        firebase_cfg = _build_firebase_config()
        app.state.firebase = firebase_cfg
        logger.info(
            "🔥 Firebase config attached: api_key_present=%s, projectId=%s, adminCredsPresent=%s",
            bool(firebase_cfg.get("apiKey")),
            firebase_cfg.get("projectId"),
            bool(firebase_cfg.get("adminCredentials")),
        )
    except Exception as e:
        logger.exception("Failed to attach Firebase config: %s", e)
        app.state.firebase = None

    logger.info("🎉 Application startup complete")
    try:
        yield  # ===== APPLICATION RUNS HERE =====
    finally:
        # ===== SHUTDOWN =====
        logger.info("🛑 Application shutdown initiated")
        try:
            await dispose_db_engine()
            logger.info("✅ Database engine disposed")
        except Exception as e:
            logger.exception("❌ Database disposal error: %s", e)
        app.state.provider_manager = None
        logger.info("👋 Application shutdown complete")


# --- FastAPI app with lifespan ---
app = FastAPI(
    title="COM-AI v3 - George's Brain",
    description="Multi-Provider AI Orchestration with Brain",
    version="3.0.0",
    lifespan=lifespan,
)

# --- CORS ---
cors_origins = getattr(settings, "cors_origins_list", None) or [
    "http://localhost:3000",
    "http://localhost:8000",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {
        "message": "COM-AI v3 - George's Brain",
        "status": "operational" if brain_available else "degraded",
        "version": "3.0.0",
        "brain_available": brain_available,
        "hints": {"db_health": "/api/health/db", "firebase_health": "/api/health/firebase"},
    }


@app.get("/api/health")
async def health_check():
    """
    Lightweight health that verifies provider configuration presence and firebase attachment.
    For deep DB checks, use /api/health/db.
    For Firebase checks, use /api/health/firebase.
    """
    providers_status = {
        "openai": {
            "configured": bool(_get_env_or_settings("OPENAI_API_KEY", "openai_api_key")),
        },
        "anthropic": {
            "configured": bool(_get_env_or_settings("ANTHROPIC_API_KEY", "anthropic_api_key")),
        },
        "gemini": {
            "configured": bool(_get_env_or_settings("GEMINI_API_KEY", "gemini_api_key")),
        },
    }

    # Firebase presence (explicit)
    fb = getattr(app.state, "firebase", None) or {}
    firebase_api_key = fb.get("apiKey")
    firebase_admin_path = fb.get("adminCredentials")

    firebase_status = {
        "attached_to_app_state": bool(fb),
        "api_key_present": bool(firebase_api_key),
        "api_key_preview": _redact(firebase_api_key),  # preview only; safe for logs
        "project_id": fb.get("projectId"),
        "auth_domain_present": bool(fb.get("authDomain")),
        "storage_bucket_present": bool(fb.get("storageBucket")),
        "admin_credentials_present": bool(firebase_admin_path),
    }

    pg_configured = bool(
        os.getenv("DATABASE_URL")
        or (os.getenv("POSTGRES_HOST") and os.getenv("POSTGRES_DB") and os.getenv("POSTGRES_USER"))
    )
    fs_configured = bool(firebase_admin_path or fb.get("projectId"))

    configured_count = sum(1 for p in providers_status.values() if p.get("configured"))
    overall_status = "healthy" if configured_count > 0 else "degraded"

    return {
        "status": overall_status,
        "brain_available": brain_available,
        "providers": {
            name: {
                **info,
                "status": "configured" if info["configured"] else "not_configured",
            } for name, info in providers_status.items()
        },
        "configured_providers": configured_count,
        "firebase": firebase_status,
        "memory": {
            "firestore": "configured" if fs_configured else "not_configured",
            "postgres": "configured" if pg_configured else "not_configured",
        },
        "hints": {
            "db_health": "/api/health/db",
            "firebase_health": "/api/health/firebase",
            "usage": "/api/health/usage"
        },
    }


# --- Mount routes ---
try:
    app.include_router(brain_router, prefix="/api/brain", tags=["brain"])
    logger.info("✅ Brain routes mounted at /api/brain")
except Exception as e:
    logger.warning(f"⚠️  Brain routes not mounted: {e}")

try:
    app.include_router(providers_router, prefix="/api", tags=["providers"])
    logger.info("✅ Providers route mounted at /api/providers")
except Exception as e:
    logger.warning(f"⚠️  Providers route not mounted: {e}")

# NEW: Mount health check routes
try:
    app.include_router(db_health_router, tags=["health"])
    logger.info("✅ DB health route mounted at /api/health/db")
except Exception as e:
    logger.warning(f"⚠️  DB health route not mounted: {e}")

try:
    app.include_router(firebase_health_router, tags=["health"])
    logger.info("✅ Firebase health route mounted at /api/health/firebase")
except Exception as e:
    logger.warning(f"⚠️  Firebase health route not mounted: {e}")

try:
    app.include_router(usage_health_router, tags=["health"])
    logger.info("✅ Usage health route mounted at /api/health/usage")
except Exception as e:
    logger.warning(f"⚠️  Usage health route not mounted: {e}")


# --- WebSocket (simple echo) ---
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            await websocket.send_text(f"Echo: {data}")
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")


if __name__ == "__main__":
    import uvicorn
    # Launch with: uvicorn --app-dir src api.main_multi:app --reload
    uvicorn.run("api.main_multi:app", host="0.0.0.0", port=8000, reload=True)