"""
API-tier Provider Orchestrator (no DB writes here)

Responsibilities:
- Normalize heterogeneous provider outputs via auto_adapter (dicts or SDK objects)
- Run strategies:
  * single  : call one provider
  * fallback: try preferred then others, stop on first success
  * all     : fan-out; deterministic winner = first success by provider order
- Return stable, typed results (dataclasses) to the route layer,
  which performs a single final telemetry write per request_id.

This replaces any prior in-provider telemetry writes (collect → write once).
"""

from __future__ import annotations

import asyncio
import time
import logging
from dataclasses import dataclass
from typing import Optional, Any, Callable, Dict, Iterable, List

logger = logging.getLogger(__name__)

# -------------------------------------------------------------------
# Stable DTOs (we do NOT mutate SDK objects)
# -------------------------------------------------------------------

@dataclass
class ProviderResult:
    provider: str
    model: Optional[str]
    text: Optional[str]
    latency_ms: int
    tokens_in: Optional[int] = None
    tokens_out: Optional[int] = None
    cost_usd: Optional[float] = None

@dataclass
class Attempt:
    seq: int
    provider: str
    model: Optional[str]
    text: Optional[str]             # "all" strategy persists per-attempt text
    status: str                     # "ok" | "error" | "not_implemented"
    latency_ms: Optional[int]
    tokens_in: Optional[int]
    tokens_out: Optional[int]
    cost_usd: Optional[float]
    error: Optional[str] = None

@dataclass
class StrategyResult:
    strategy: str                   # "single" | "fallback" | "all"
    elapsed_ms: int
    winner: Optional[ProviderResult]
    attempts: List[Attempt]

# -------------------------------------------------------------------
# Utilities
# -------------------------------------------------------------------

def _sum_i(values: Iterable[Optional[int | float]]) -> int:
    return int(sum(v for v in values if isinstance(v, (int, float))))

def _sum_f(values: Iterable[Optional[int | float]]) -> float:
    return float(sum(v for v in values if isinstance(v, (int, float))))

Extractor = Callable[[str, Any, int], ProviderResult]

# -------------------------------------------------------------------
# Auto-adapter: handles dict-returning wrappers and common SDK shapes
# -------------------------------------------------------------------

def auto_adapter(pid: str, raw: Any, latency_ms: int) -> ProviderResult:
    # Dict-returning wrappers (e.g., your BaseProvider.generate returns a dict)
    if isinstance(raw, dict):
        text = raw.get("text") or raw.get("content") or raw.get("output")
        model = raw.get("model")
        usage = raw.get("usage") or {}
        tokens_in = raw.get("tokens_in", usage.get("prompt_tokens"))
        tokens_out = raw.get("tokens_out", usage.get("completion_tokens"))
        cost_usd = raw.get("cost_usd")
        if text is None:
            logger.warning("auto_adapter: no text extracted for provider=%s raw_type=dict", pid)
        return ProviderResult(pid, model, text, latency_ms, tokens_in, tokens_out, cost_usd)

    # SDK objects (best-effort)
    text = None
    for attr in ("text", "content", "output"):
        text = getattr(raw, attr, None)
        if text:
            break

    # OpenAI Chat Completions: choices[0].message.content
    if not text and hasattr(raw, "choices") and raw.choices:
        ch0 = raw.choices[0]
        msg = getattr(ch0, "message", None)
        text = getattr(msg, "content", None) if msg else None

    # Anthropic Messages: list of blocks with .text
    if not text and hasattr(raw, "content"):
        blocks = getattr(raw, "content")
        if isinstance(blocks, list) and blocks:
            parts = []
            for b in blocks:
                t = getattr(b, "text", None) if hasattr(b, "text") else (b.get("text") if isinstance(b, dict) else None)
                if t:
                    parts.append(t)
            text = "\n".join(parts) if parts else None

    # Gemini-style candidates (optional)
    if not text and hasattr(raw, "candidates") and raw.candidates:
        cand0 = raw.candidates[0]
        text = getattr(cand0, "content", None) or getattr(cand0, "text", None)

    if text is None:
        logger.warning("auto_adapter: no text extracted for provider=%s raw_type=%s", pid, type(raw))

    model = getattr(raw, "model", None)
    usage = getattr(raw, "usage", None)
    tokens_in = None
    tokens_out = None
    if usage is not None:
        tokens_in  = getattr(usage, "prompt_tokens", None) or getattr(usage, "input_tokens", None)
        tokens_out = getattr(usage, "completion_tokens", None) or getattr(usage, "output_tokens", None)
    cost_usd = getattr(raw, "cost_usd", None)

    return ProviderResult(pid, model, text, latency_ms, tokens_in, tokens_out, cost_usd)

# -------------------------------------------------------------------
# ProviderManager (API-tier orchestrator)
# -------------------------------------------------------------------

class ProviderManager:
    """
    Holds provider wrappers (instances implementing async .generate()) and
    orchestrates calls. No DB writes here—route layer handles telemetry.
    """

    def __init__(self, providers: Dict[str, Any], adapters: Optional[Dict[str, Extractor]] = None):
        self.providers = providers
        self.adapters = adapters or {}

    def _extract(self, provider_id: str, raw: Any, latency_ms: int) -> ProviderResult:
        extractor = self.adapters.get(provider_id, auto_adapter)
        return extractor(provider_id, raw, latency_ms)

    async def _call_one(self, provider_id: str, prompt: str, **kwargs) -> ProviderResult:
        if provider_id not in self.providers:
            raise KeyError(f"Unknown provider_id '{provider_id}'")
        t0 = time.perf_counter()
        raw = await self.providers[provider_id].generate(prompt, **kwargs)
        latency_ms = int((time.perf_counter() - t0) * 1000)
        return self._extract(provider_id, raw, latency_ms)

    async def generate_from_provider(self, provider_id: str, prompt: str, **kwargs) -> StrategyResult:
        out = await self._call_one(provider_id, prompt, **kwargs)
        attempts = [Attempt(
            seq=0, provider=provider_id, model=out.model, text=out.text, status="ok",
            latency_ms=out.latency_ms, tokens_in=out.tokens_in,
            tokens_out=out.tokens_out, cost_usd=out.cost_usd, error=None
        )]
        return StrategyResult(strategy="single", elapsed_ms=out.latency_ms, winner=out, attempts=attempts)

    async def generate_with_fallback(self, prompt: str, *, preferred: str, **kwargs) -> StrategyResult:
        t0 = time.perf_counter()
        attempts: List[Attempt] = []
        tried = [preferred] + [p for p in self.providers.keys() if p != preferred]
        winner: Optional[ProviderResult] = None

        for seq, pid in enumerate(tried):
            try:
                out = await self._call_one(pid, prompt, **kwargs)
                attempts.append(Attempt(
                    seq=seq, provider=pid, model=out.model, text=out.text, status="ok",
                    latency_ms=out.latency_ms, tokens_in=out.tokens_in,
                    tokens_out=out.tokens_out, cost_usd=out.cost_usd, error=None
                ))
                winner = out
                break
            except NotImplementedError as e:
                attempts.append(Attempt(seq=seq, provider=pid, model=None, text=None,
                                        status="not_implemented", latency_ms=None,
                                        tokens_in=None, tokens_out=None, cost_usd=None, error=str(e)))
            except Exception as e:
                attempts.append(Attempt(seq=seq, provider=pid, model=None, text=None,
                                        status="error", latency_ms=None,
                                        tokens_in=None, tokens_out=None, cost_usd=None, error=str(e)))

        elapsed_ms = int((time.perf_counter() - t0) * 1000)
        attempts = sorted(attempts, key=lambda a: a.seq)
        return StrategyResult(strategy="fallback", elapsed_ms=elapsed_ms, winner=winner, attempts=attempts)

    async def generate_from_all(self, prompt: str, **kwargs) -> StrategyResult:
        """
        Deterministic: gather keeps result order == provider_ids order,
        then pick the first successful ProviderResult in that order.
        """
        t0 = time.perf_counter()
        attempts: List[Attempt] = []
        provider_ids = list(self.providers.keys())

        async def run_one(seq: int, pid: str):
            try:
                out = await self._call_one(pid, prompt, **kwargs)
                attempts.append(Attempt(
                    seq=seq, provider=pid, model=out.model, text=out.text, status="ok",
                    latency_ms=out.latency_ms, tokens_in=out.tokens_in,
                    tokens_out=out.tokens_out, cost_usd=out.cost_usd, error=None
                ))
                return out
            except NotImplementedError as e:
                attempts.append(Attempt(seq=seq, provider=pid, model=None, text=None,
                                        status="not_implemented", latency_ms=None,
                                        tokens_in=None, tokens_out=None, cost_usd=None, error=str(e)))
                return e
            except Exception as e:
                attempts.append(Attempt(seq=seq, provider=pid, model=None, text=None,
                                        status="error", latency_ms=None,
                                        tokens_in=None, tokens_out=None, cost_usd=None, error=str(e)))
                return e

        tasks = [run_one(i, pid) for i, pid in enumerate(provider_ids)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        winner: Optional[ProviderResult] = next((r for r in results if isinstance(r, ProviderResult)), None)
        elapsed_ms = int((time.perf_counter() - t0) * 1000)
        attempts = sorted(attempts, key=lambda a: a.seq)
        return StrategyResult(strategy="all", elapsed_ms=elapsed_ms, winner=winner, attempts=attempts)