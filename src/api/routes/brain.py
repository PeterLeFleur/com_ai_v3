""" 
Brain routes: synthesis and related endpoints with PostgreSQL persistence and telemetry.
"""
from fastapi import APIRouter, Request, HTTPException, Query, Depends
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from uuid import UUID, uuid4
import logging

from sqlalchemy.ext.asyncio import AsyncSession
from src.api.db.session import get_db_session_dependency as get_db
from src.api.db import dal

router = APIRouter()
logger = logging.getLogger(__name__)

class SynthesizeRequest(BaseModel):
    prompt: str = Field(..., description="User prompt to synthesize across providers")
    rounds: int = Field(1, ge=1, le=10, description="Number of synthesis rounds")
    user_id: Optional[str] = Field(None, description="External user identifier (e.g., OAuth ID)")
    session_id: Optional[UUID] = Field(None, description="Existing session UUID to continue")

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
    request_id: UUID
    session_id: UUID
    user_id: UUID

@router.post("/synthesize", response_model=SynthesizeResponse)
async def synthesize(
    req: SynthesizeRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    provider: Optional[str] = Query(None, description="preferred provider id"),
    model: Optional[str] = Query(None, description="model override"),
    temperature: Optional[float] = Query(None, ge=0.0, le=2.0, description="temperature override"),
    fallback: bool = Query(True, description="allow fallback if preferred fails")
) -> SynthesizeResponse:
    pm = getattr(request.app.state, "provider_manager", None)
    if not pm:
        raise HTTPException(status_code=503, detail="ProviderManager not initialized")

    if not getattr(pm, "providers", {}):
        no_providers = ProviderResult(
            provider="none",
            status="noop",
            text="No providers registered. Add API keys in .env and restart the server."
        )
        return SynthesizeResponse(
            status="ok",
            rounds_completed=req.rounds,
            results=[no_providers],
            request_id=uuid4(),
            session_id=uuid4(),
            user_id=uuid4()
        )

    # Generate unique request ID for tracing
    request_id = uuid4()

    # User management: get or create user
    external_user_id = req.user_id or "anonymous"
    user = await dal.get_or_create_user(db, external_id=external_user_id, role="user")

    # Session management: get existing or create new
    if req.session_id:
        session = await dal.get_session(db, req.session_id)
        if session is None:
            raise HTTPException(status_code=404, detail=f"Session {req.session_id} not found")
        await dal.update_session_activity(db, req.session_id)
    else:
        title = f"Synthesis: {req.prompt[:50]}..."
        session = await dal.create_session(db, user_id=user.id, title=title)

    # Persist user message to database
    user_message = await dal.append_message(
        db,
        session_id=session.id,
        role="user",
        content=req.prompt,
        request_id=request_id
    )

    # Use selective generation based on preferences
    kwargs = {}
    if model: 
        kwargs["model"] = model
    if temperature is not None: 
        kwargs["temperature"] = temperature

    # === DIAGNOSTIC LOGGING - REMOVE AFTER DEBUGGING ===
    logger.info("="*60)
    logger.info("STRATEGY ROUTING DEBUG")
    logger.info(f"provider value: {repr(provider)}")
    logger.info(f"provider type: {type(provider)}")
    logger.info(f"provider bool: {bool(provider)}")
    logger.info(f"fallback value: {repr(fallback)}")
    logger.info(f"fallback type: {type(fallback)}")
    logger.info(f"fallback bool: {bool(fallback)}")
    logger.info(f"Test: (provider and not fallback) = {bool(provider and not fallback)}")
    logger.info(f"Test: (provider and fallback) = {bool(provider and fallback)}")
    logger.info(f"Test: else case = {not (provider and not fallback) and not (provider and fallback)}")
    logger.info("="*60)

    # Execute strategy and get StrategyResult
    if provider and not fallback:
        logger.info("→ EXECUTING: generate_from_provider (single)")
        strategy_result = await pm.generate_from_provider(provider, req.prompt, **kwargs)
    elif provider and fallback:
        logger.info("→ EXECUTING: generate_with_fallback")
        strategy_result = await pm.generate_with_fallback(req.prompt, preferred=provider, **kwargs)
    else:
        logger.info("→ EXECUTING: generate_from_all")
        strategy_result = await pm.generate_from_all(req.prompt, **kwargs)

    logger.info(f"RESULT: strategy_result.strategy = {strategy_result.strategy}")
    logger.info("="*60)
    # === END DIAGNOSTIC LOGGING ===

    # Process results from attempts
    results: List[ProviderResult] = []
    for attempt in strategy_result.attempts:
        # Build usage dict from tokens
        usage_data = None
        if attempt.tokens_in is not None or attempt.tokens_out is not None:
            usage_data = {
                "prompt_tokens": attempt.tokens_in,
                "completion_tokens": attempt.tokens_out
            }

        # Persist assistant message to database if successful
        if attempt.text and attempt.status == "ok":
            await dal.append_message(
                db,
                session_id=session.id,
                role="assistant",
                content=attempt.text,
                provider=attempt.provider,
                model=attempt.model,
                tokens_in=attempt.tokens_in,
                tokens_out=attempt.tokens_out,
                latency_ms=attempt.latency_ms,
                request_id=request_id
            )

        results.append(
            ProviderResult(
                provider=attempt.provider,
                status=attempt.status,
                text=attempt.text,
                model=attempt.model,
                latency_ms=attempt.latency_ms,
                usage=usage_data,
                error=attempt.error
            )
        )

    return SynthesizeResponse(
        status="ok",
        rounds_completed=req.rounds,
        results=results,
        request_id=request_id,
        session_id=session.id,
        user_id=user.id
    )

@router.get("/synthesize", response_model=SynthesizeResponse)
async def synthesize_get(
    prompt: str,
    rounds: int = 1,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    user_id: Optional[str] = Query(None, description="External user identifier"),
    session_id: Optional[UUID] = Query(None, description="Existing session UUID"),
    provider: Optional[str] = Query(None, description="preferred provider id"),
    model: Optional[str] = Query(None, description="model override"),
    temperature: Optional[float] = Query(None, ge=0.0, le=2.0, description="temperature override"),
    fallback: bool = Query(True, description="allow fallback if preferred fails")
) -> SynthesizeResponse:
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
        return SynthesizeResponse(
            status="ok",
            rounds_completed=rounds,
            results=[no_providers],
            request_id=uuid4(),
            session_id=uuid4(),
            user_id=uuid4()
        )

    # Generate unique request ID for tracing
    request_id = uuid4()

    # User management: get or create user
    external_user_id = user_id or "anonymous"
    user = await dal.get_or_create_user(db, external_id=external_user_id, role="user")

    # Session management: get existing or create new
    if session_id:
        session = await dal.get_session(db, session_id)
        if session is None:
            raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
        await dal.update_session_activity(db, session_id)
    else:
        title = f"Synthesis: {prompt[:50]}..."
        session = await dal.create_session(db, user_id=user.id, title=title)

    # Persist user message
    user_message = await dal.append_message(
        db,
        session_id=session.id,
        role="user",
        content=prompt,
        request_id=request_id
    )

    # Use selective generation based on preferences
    kwargs = {}
    if model: 
        kwargs["model"] = model
    if temperature is not None: 
        kwargs["temperature"] = temperature

    # Execute strategy and get StrategyResult
    if provider and not fallback:
        strategy_result = await pm.generate_from_provider(provider, prompt, **kwargs)
    elif provider and fallback:
        strategy_result = await pm.generate_with_fallback(prompt, preferred=provider, **kwargs)
    else:
        strategy_result = await pm.generate_from_all(prompt, **kwargs)

    # Process results from attempts
    results: List[ProviderResult] = []
    for attempt in strategy_result.attempts:
        # Build usage dict from tokens
        usage_data = None
        if attempt.tokens_in is not None or attempt.tokens_out is not None:
            usage_data = {
                "prompt_tokens": attempt.tokens_in,
                "completion_tokens": attempt.tokens_out
            }

        # Persist assistant message
        if attempt.text and attempt.status == "ok":
            await dal.append_message(
                db,
                session_id=session.id,
                role="assistant",
                content=attempt.text,
                provider=attempt.provider,
                model=attempt.model,
                tokens_in=attempt.tokens_in,
                tokens_out=attempt.tokens_out,
                latency_ms=attempt.latency_ms,
                request_id=request_id
            )

        results.append(
            ProviderResult(
                provider=attempt.provider,
                status=attempt.status,
                text=attempt.text,
                model=attempt.model,
                latency_ms=attempt.latency_ms,
                usage=usage_data,
                error=attempt.error
            )
        )

    return SynthesizeResponse(
        status="ok",
        rounds_completed=rounds,
        results=results,
        request_id=request_id,
        session_id=session.id,
        user_id=user.id
    )