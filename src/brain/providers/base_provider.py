"""
COM-AI v3 - Base Provider Interface
Abstract base class for all AI providers.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import time


class BaseProvider(ABC):
    """
    Base class for AI providers.

    __init__ here is concrete so subclasses can pass common fields.
    Always call: super().__init__(name=..., api_key=..., model=...)
    """

    def __init__(self, *, name: str, api_key: Optional[str] = None, model: Optional[str] = None):
        self.name = name
        self.api_key = api_key or ""
        self.model = model or ""
        self._last_health_check: Optional[float] = None
        self._is_healthy: Optional[bool] = None

    @abstractmethod
    async def generate(self, prompt: str, **kwargs) -> Dict[str, Any]:
        """
        Generate response from provider.

        Returns:
            {
                "text": str,
                "model": str,
                "latency_ms": int,
                "usage": Dict[str, Any],
                "provider": str,
                "status": "success" | "error" | "timeout"
            }
        """
        raise NotImplementedError

    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """
        Check provider health/connectivity. Must be awaitable.

        Returns:
            {
                "provider": str,
                "status": "healthy" | "error" | "not_configured",
                "configured": bool,
                "reachable": bool,
                "error": Optional[str]
            }
        """
        raise NotImplementedError

    # Compatibility alias (some code may call get_health)
    async def get_health(self) -> Dict[str, Any]:
        return await self.health_check()

    def _start_timer(self) -> float:
        return time.time()

    def _end_timer(self, start_time: float) -> int:
        return int((time.time() - start_time) * 1000)
