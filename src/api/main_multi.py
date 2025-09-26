"""
COM-AI v3 - George's Brain Multi-Provider Orchestrator
Main entry point for the brain-enabled API server
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from src.utils.config import get_settings
from src.utils.logging_config import setup_logging
import logging

# Logging & settings
setup_logging()
logger = logging.getLogger(__name__)
settings = get_settings()

# FastAPI app
app = FastAPI(
    title="COM-AI v3 - George's Brain",
    description="Multi-Provider AI Orchestration with Brain",
    version="3.0.0",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

brain_available = False


def _register_openai(pm):
    if not settings.openai_api_key:
        logger.info("OpenAI: no API key configured; skipping.")
        return False
    try:
        from src.brain.providers.openai_provider import OpenAIProvider
    except Exception as e:
        logger.warning(f"OpenAI import failed; skipping: {e}")
        return False
    try:
        pm.register_provider(
            OpenAIProvider(
                api_key=settings.openai_api_key,
                model=getattr(settings, "openai_model", "gpt-4o-mini"),
            )
        )
        logger.info("OpenAI provider registered")
        return True
    except Exception as e:
        logger.warning(f"OpenAI registration failed; skipping: {e}")
        return False


def _register_anthropic(pm):
    if not getattr(settings, "anthropic_api_key", None):
        logger.info("Anthropic: no API key configured; skipping.")
        return False
    try:
        from src.brain.providers.anthropic_provider import AnthropicProvider
    except Exception as e:
        logger.warning(f"Anthropic import failed; skipping: {e}")
        return False
    try:
        pm.register_provider(
            AnthropicProvider(
                api_key=settings.anthropic_api_key,
                model=getattr(settings, "anthropic_model", "claude-3-5-sonnet-20240620"),
            )
        )
        logger.info("Anthropic provider registered")
        return True
    except Exception as e:
        logger.warning(f"Anthropic registration failed; skipping: {e}")
        return False


def _register_gemini(pm):
    if not getattr(settings, "gemini_api_key", None):
        logger.info("Gemini: no API key configured; skipping.")
        return False
    try:
        from src.brain.providers.gemini_provider import GeminiProvider
    except Exception as e:
        logger.warning(f"Gemini import failed; skipping: {e}")
        return False
    try:
        pm.register_provider(
            GeminiProvider(
                api_key=settings.gemini_api_key,
                model=getattr(settings, "gemini_model", "gemini-1.5-pro"),
            )
        )
        logger.info("Gemini provider registered")
        return True
    except Exception as e:
        logger.warning(f"Gemini registration failed; skipping: {e}")
        return False


@app.on_event("startup")
async def startup() -> None:
    """
    Initialize brain + provider manager and register configured providers.
    Registration is fully resilient: failures in one provider never block others.
    """
    global brain_available
    try:
        from src.brain.cerebrum.cadre import CerebrumCadre
        from src.brain.providers.manager import ProviderManager

        app.state.brain = CerebrumCadre()
        app.state.provider_manager = ProviderManager()
        pm = app.state.provider_manager

        # Try each provider independently. Any failure is logged and ignored.
        registered = {
            "openai": _register_openai(pm),
            "anthropic": _register_anthropic(pm),
            "gemini": _register_gemini(pm),
        }
        total_registered = sum(1 for ok in registered.values() if ok)
        logger.info(f"Provider registration summary: {registered} (total={total_registered})")

        brain_available = True
        logger.info("Brain and ProviderManager initialized")
    except Exception as e:
        logger.warning(f"Brain setup failed: {e}")
        brain_available = False


@app.get("/")
async def root():
    return {
        "message": "COM-AI v3 - George's Brain",
        "status": "operational",
        "version": "3.0.0",
        "brain_available": brain_available,
    }


@app.get("/api/health")
async def health_check():
    """
    Comprehensive health check with real provider status.
    Uses configuration presence + provider_manager health probes (if available).
    """
    providers_status = {
        "openai": {
            "configured": bool(getattr(settings, "openai_api_key", None)),
            "status": "configured" if getattr(settings, "openai_api_key", None) else "not_configured",
        },
        "anthropic": {
            "configured": bool(getattr(settings, "anthropic_api_key", None)),
            "status": "configured" if getattr(settings, "anthropic_api_key", None) else "not_configured",
        },
        "gemini": {
            "configured": bool(getattr(settings, "gemini_api_key", None)),
            "status": "configured" if getattr(settings, "gemini_api_key", None) else "not_configured",
        },
    }

    # Augment with live health if provider manager exists
    pm = getattr(app.state, "provider_manager", None)
    if pm:
        try:
            live = await pm.get_all_health_status()
            for name, info in live.items():
                providers_status[name] = {
                    "configured": info.get("configured", providers_status.get(name, {}).get("configured", False)),
                    "status": info.get("status", "error"),
                    "reachable": info.get("reachable", False),
                    "error": info.get("error"),
                }
        except Exception as e:
            logger.warning(f"Provider live health failed: {e}")

    configured_count = sum(1 for p in providers_status.values() if p.get("configured"))
    overall_status = "healthy" if configured_count > 0 else "degraded"

    return {
        "status": overall_status,
        "brain_available": brain_available,
        "providers": providers_status,
        "configured_providers": configured_count,
        "memory": {"firestore": "not_configured", "postgres": "not_configured"},
    }


# WebSocket (simple echo)
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            await websocket.send_text(f"Echo: {data}")
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")


# Mount brain routes
try:
    from src.api.routes.brain import router as brain_router
    app.include_router(brain_router, prefix="/api/brain", tags=["brain"])
    logger.info("Brain routes mounted at /api/brain")
except Exception as e:
    logger.warning(f"Brain routes not mounted yet: {e}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.api.main_multi:app", host="0.0.0.0", port=8000, reload=True)
