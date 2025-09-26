""" 
Brain routes: synthesis and related endpoints.
"""
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional

router = APIRouter()

class SynthesizeRequest(BaseModel):
    prompt: str = Field(..., description="User prompt to synthesize across providers")
    rounds: int = Field(1, ge=1, le=10, description="Number of synthesis rounds")

class ProviderResult(BaseModel):
    provider: str
    status: str
    text: Optional[str] = None
    model: Optional[str] = None
    latency_ms: Optional[int] = None
    usage: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

class SynthesizeResponse(BaseModel):
    status: str
    rounds_completed: int
    results: List[ProviderResult]

@router.post("/synthesize", response_model=SynthesizeResponse)
async def synthesize(req: SynthesizeRequest, request: Request) -> SynthesizeResponse:
    pm = getattr(request.app.state, "provider_manager", None)
    if not pm:
        raise HTTPException(status_code=503, detail="ProviderManager not initialized")

    if not getattr(pm, "providers", {}):
        no_providers = ProviderResult(
            provider="none",
            status="noop",
            text="No providers registered. Add API keys in .env and restart the server."
        )
        return SynthesizeResponse(status="ok", rounds_completed=req.rounds, results=[no_providers])

    raw_results = await pm.generate_from_all(req.prompt)

    results: List[ProviderResult] = []
    for r in raw_results:
        results.append(
            ProviderResult(
                provider=r.get("provider") or r.get("name") or "unknown",
                status=r.get("status", "error"),
                text=r.get("text"),
                model=r.get("model"),
                latency_ms=r.get("latency_ms"),
                usage=r.get("usage"),
                error=r.get("error"),
            )
        )

    return SynthesizeResponse(status="ok", rounds_completed=req.rounds, results=results)

@router.get("/synthesize", response_model=SynthesizeResponse)
async def synthesize_get(prompt: str, rounds: int = 1, request: Request = None) -> SynthesizeResponse:
    if request is None:
        raise HTTPException(status_code=500, detail="Request not available")
    pm = getattr(request.app.state, "provider_manager", None)
    if not pm:
        raise HTTPException(status_code=503, detail="ProviderManager not initialized")

    if not getattr(pm, "providers", {}):
        no_providers = ProviderResult(
            provider="none",
            status="noop",
            text="No providers registered. Add API keys in .env and restart the server."
        )
        return SynthesizeResponse(status="ok", rounds_completed=rounds, results=[no_providers])

    raw_results = await pm.generate_from_all(prompt)
    results: List[ProviderResult] = []
    for r in raw_results:
        results.append(
            ProviderResult(
                provider=r.get("provider") or r.get("name") or "unknown",
                status=r.get("status", "error"),
                text=r.get("text"),
                model=r.get("model"),
                latency_ms=r.get("latency_ms"),
                usage=r.get("usage"),
                error=r.get("error"),
            )
        )
    return SynthesizeResponse(status="ok", rounds_completed=rounds, results=results)
