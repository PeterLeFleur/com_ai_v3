"""
COM-AI v3 - Anthropic Provider
Implements real Anthropic API calls via the anthropic library.
"""

from typing import Dict, Any, Optional
import time

from .base_provider import BaseProvider

class AnthropicProvider(BaseProvider):
    def __init__(self, api_key: str, model: str = "claude-3-5-sonnet-20241022"):
        super().__init__(name="anthropic", api_key=api_key, model=model)

    async def generate(self, prompt: str, **kwargs) -> Dict[str, Any]:
        if not self.api_key:
            return {
                "provider": self.name,
                "status": "error",
                "error": "No API key configured",
                "model": self.model,
            }

        # Allow per-call overrides
        model: str = kwargs.get("model", self.model) or self.model
        temperature: Optional[float] = kwargs.get("temperature", 0.7)

        try:
            # anthropic client is sync; tiny calls are OK,
            # but we still time them and return usage/latency
            import anthropic

            start = time.time()
            client = anthropic.Anthropic(api_key=self.api_key)

            resp = client.messages.create(
                model=model,
                max_tokens=1000,
                temperature=temperature,
                messages=[{"role": "user", "content": prompt}],
            )

            latency_ms = int((time.time() - start) * 1000)

            # Response content is a list of message blocks; take first text block
            text = ""
            if resp.content and len(resp.content) > 0:
                # Newer SDKs return TextBlock with .text
                first = resp.content[0]
                text = getattr(first, "text", "") if hasattr(first, "text") else str(first)

            usage = {}
            try:
                usage = {
                    "input_tokens": getattr(resp.usage, "input_tokens", None),
                    "output_tokens": getattr(resp.usage, "output_tokens", None),
                    "total_tokens": (
                        getattr(resp.usage, "input_tokens", 0)
                        + getattr(resp.usage, "output_tokens", 0)
                        if getattr(resp, "usage", None) else None
                    ),
                }
            except Exception:
                pass

            return {
                "provider": self.name,
                "status": "success",
                "text": text,
                "model": model,
                "latency_ms": latency_ms,
                "usage": usage,
            }

        except ImportError:
            return {
                "provider": self.name,
                "status": "error",
                "error": "anthropic library not installed. Run: python -m pip install anthropic",
                "model": model,
            }
        except Exception as e:
            return {
                "provider": self.name,
                "status": "error",
                "error": f"Anthropic API error: {e}",
                "model": model,
            }

    async def health_check(self) -> Dict[str, Any]:
        if not self.api_key:
            return {
                "provider": self.name,
                "status": "not_configured",
                "configured": False,
                "reachable": False,
                "error": "No API key configured",
            }

        # Cheap-ish live check: very small completion
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=self.api_key)
            _ = client.messages.create(
                model=self.model or "claude-3-5-sonnet-20241022",
                max_tokens=1,
                messages=[{"role": "user", "content": "ping"}],
            )
            return {
                "provider": self.name,
                "status": "healthy",
                "configured": True,
                "reachable": True,
                "error": None,
            }
        except ImportError:
            return {
                "provider": self.name,
                "status": "error",
                "configured": True,
                "reachable": False,
                "error": "anthropic library not installed",
            }
        except Exception as e:
            return {
                "provider": self.name,
                "status": "error",
                "configured": True,
                "reachable": False,
                "error": f"Auth/API error: {e}",
            }

    async def get_health(self) -> Dict[str, Any]:
        return await self.health_check()
