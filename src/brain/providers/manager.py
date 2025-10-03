"""
Shim for backward compatibility.

Re-exports the API-tier ProviderManager so legacy imports under
`src.brain.providers.manager` keep working while orchestration lives in:

  src/api/brain/providers/manager.py

Prefer importing from `src.api.brain.providers.manager` going forward.
"""

from src.api.brain.providers.manager import (
    ProviderManager,
    ProviderResult,
    StrategyResult,
    Attempt,
    auto_adapter,
)

__all__ = [
    "ProviderManager",
    "ProviderResult",
    "StrategyResult",
    "Attempt",
    "auto_adapter",
]
