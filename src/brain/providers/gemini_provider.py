"""
COM-AI v3 - Gemini Provider
"""
from typing import Dict, Any
import logging
import asyncio
import google.generativeai as genai
from .base_provider import BaseProvider

logger = logging.getLogger(__name__)

class GeminiProvider(BaseProvider):
    def __init__(self, api_key: str, model: str = "gemini-1.5-flash"):
        super().__init__(name="gemini", api_key=api_key, model=model)
        genai.configure(api_key=api_key)
        self.client = genai.GenerativeModel(model)

    async def generate(self, prompt: str, **kwargs) -> Dict[str, Any]:
        try:
            # Wrap API call with 30-second timeout
            response = await asyncio.wait_for(
                self.client.generate_content_async(prompt),
                timeout=30.0
            )
            
            # DEBUG: Log the actual response structure
            logger.info(f"GEMINI DEBUG: response type = {type(response)}")
            logger.info(f"GEMINI DEBUG: response dir = {dir(response)}")
            
            # Try different ways to extract text
            text = None
            if hasattr(response, 'text'):
                text = response.text
                logger.info(f"GEMINI DEBUG: Found text via .text attribute: {text[:100] if text else 'None'}")
            elif hasattr(response, 'candidates') and response.candidates:
                text = response.candidates[0].content.parts[0].text
                logger.info(f"GEMINI DEBUG: Found text via candidates: {text[:100] if text else 'None'}")
            
            if not text:
                logger.warning("GEMINI DEBUG: No text extracted, returning empty string")
                text = ""
            
            return {
                "text": text,
                "model": self.model,
                "provider": self.name,
            }
            
        except asyncio.TimeoutError:
            logger.error(f"GEMINI TIMEOUT: API call exceeded 30 seconds")
            return {
                "provider": self.name,
                "status": "error",
                "error": "Gemini API timeout after 30 seconds",
                "model": self.model,
                "text": None,
            }
        except Exception as e:
            logger.error(f"GEMINI ERROR: {e}", exc_info=True)
            return {
                "provider": self.name,
                "status": "error",
                "error": str(e),
                "model": self.model,
                "text": None,
            }

    async def health_check(self) -> Dict[str, Any]:
        return {
            "provider": self.name,
            "status": "healthy" if self.api_key else "not_configured",
            "configured": bool(self.api_key),
            "reachable": bool(self.api_key),
            "error": None if self.api_key else "No API key configured",
        }

    async def get_health(self) -> Dict[str, Any]:
        return await self.health_check()