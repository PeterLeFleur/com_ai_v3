"""
COM-AI v3 - Provider Management Routes
"""

from fastapi import APIRouter, Request

router = APIRouter()

@router.get("/providers")
async def list_providers(request: Request):
    """
    List available AI providers currently registered in ProviderManager.
    """
    pm = getattr(request.app.state, "provider_manager", None)
    if pm is None:
        return {"providers": [], "total": 0, "status": "provider_manager_unavailable"}

    providers = []
    for name, inst in pm.providers.items():
        providers.append({
            "name": name,
            "configured": bool(getattr(inst, "api_key", None)),
            "default_model": getattr(inst, "model", None),
        })

    return {"providers": providers, "total": len(providers), "status": "ok"}
