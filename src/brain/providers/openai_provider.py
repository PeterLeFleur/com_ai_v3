"""
COM-AI v3 - OpenAI Provider
Implements BaseProvider using the official OpenAI Python SDK (v1.x).
"""

from typing import Dict, Any, Optional
import asyncio

from openai import (
    AsyncOpenAI,
    APIError,
    APIConnectionError,
    RateLimitError,
    AuthenticationError,
)

from .base_provider import BaseProvider


class OpenAIProvider(BaseProvider):
    """
    OpenAI provider implementation.
    - generate(): calls Chat Completions with minimal params
    - health_check(): attempts a tiny completion to verify reachability
    - get_health(): compatibility alias if BaseProvider requires it
    """

    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        super().__init__(name="openai", api_key=api_key, model=model)
        # Build a client per provider instance
        self._client = AsyncOpenAI(api_key=self.api_key)

    async def generate(self, prompt: str, **kwargs) -> Dict[str, Any]:
        """
        Generate a response from OpenAI Chat Completions.
        Returns a dict shaped for ProviderManager consumption.
        """
        start = self._start_timer()
        try:
            # You can pass additional kwargs (e.g., temperature) via **kwargs
            resp = await self._client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=256,
                **{k: v for k, v in kwargs.items() if v is not None},
            )

            text: Optional[str] = None
            if resp and getattr(resp, "choices", None):
                # SDK v1.x returns choices[0].message.content
                text = (resp.choices[0].message.content or "").strip()

            latency_ms = self._end_timer(start)

            usage: Dict[str, Any] = {}
            try:
                if hasattr(resp, "usage") and resp.usage:
                    usage = {
                        "prompt_tokens": getattr(resp.usage, "prompt_tokens", None),
                        "completion_tokens": getattr(resp.usage, "completion_tokens", None),
                        "total_tokens": getattr(resp.usage, "total_tokens", None),
                    }
            except Exception:
                usage = {}

            return {
                "provider": self.name,
                "text": text,
                "model": self.model,
                "latency_ms": latency_ms,
                "usage": usage,
            }

        except (AuthenticationError, RateLimitError, APIConnectionError, APIError) as e:
            # Known OpenAI API errors
            return {
                "provider": self.name,
                "status": "error",
                "error": f"{type(e).__name__}: {str(e)}",
                "model": self.model,
            }
        except asyncio.TimeoutError:
            return {
                "provider": self.name,
                "status": "timeout",
                "error": "Timeout while contacting OpenAI",
                "model": self.model,
            }
        except Exception as e:
            return {
                "provider": self.name,
                "status": "error",
                "error": f"Unexpected: {str(e)}",
                "model": self.model,
            }

    async def health_check(self) -> Dict[str, Any]:
        """
        Attempts a very small completion to verify credentials + reachability.
        Keeps it cheap: max_tokens=1.
        """
        try:
            _ = await self._client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=1,
            )
            self._is_healthy = True
            return {
                "provider": self.name,
                "status": "healthy",
                "configured": True,
                "reachable": True,
                "error": None,
            }
        except AuthenticationError as e:
            self._is_healthy = False
            return {
                "provider": self.name,
                "status": "error",
                "configured": True,
                "reachable": False,
                "error": f"Auth error: {e}",
            }
        except (RateLimitError, APIConnectionError, APIError) as e:
            self._is_healthy = False
            return {
                "provider": self.name,
                "status": "error",
                "configured": True,
                "reachable": False,
                "error": str(e),
            }
        except Exception as e:
            self._is_healthy = False
            return {
                "provider": self.name,
                "status": "error",
                "configured": True,
                "reachable": False,
                "error": f"Unexpected: {e}",
            }

    # Some versions of BaseProvider may require this method explicitly.
    # Keep it as a thin alias to health_check for compatibility.
    async def get_health(self) -> Dict[str, Any]:
        return await self.health_check()
