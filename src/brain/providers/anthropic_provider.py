"""
COM-AI v3 - Anthropic Provider (stub)
Implements BaseProvider shape so registration & health work.
Upgrade generate() later to call real Anthropic API.
"""
from typing import Dict, Any
from .base_provider import BaseProvider

class AnthropicProvider(BaseProvider):
    def __init__(self, api_key: str, model: str = "claude-3-5-sonnet-20240620"):
        super().__init__(name="anthropic", api_key=api_key, model=model)

    async def generate(self, prompt: str, **kwargs) -> Dict[str, Any]:
        # TODO: implement real Anthropic call
        return {
            "provider": self.name,
            "status": "error",
            "error": "not_implemented",
            "model": self.model,
        }

    async def health_check(self) -> Dict[str, Any]:
        # Minimal “configured” signal until real ping implemented
        return {
            "provider": self.name,
            "status": "healthy" if self.api_key else "not_configured",
            "configured": bool(self.api_key),
            "reachable": bool(self.api_key),
            "error": None if self.api_key else "No API key configured",
        }

    async def get_health(self) -> Dict[str, Any]:
        return await self.health_check()
