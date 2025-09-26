"""
COM-AI v3 - Provider Manager
Orchestrates multiple AI providers with graceful degradation
"""

from typing import Dict, List, Any, Optional
import asyncio
import logging
from .base_provider import BaseProvider

logger = logging.getLogger(__name__)

class ProviderManager:
    """Manages multiple AI providers with fault tolerance"""
    
    def __init__(self):
        self.providers: Dict[str, BaseProvider] = {}
        self.timeout_seconds = 30
        self.max_retries = 2
        logger.info("ProviderManager initialized")
    
    def register_provider(self, provider: BaseProvider):
        """Register a provider"""
        self.providers[provider.name] = provider
        logger.info(f"Registered provider: {provider.name}")
    
    def get_provider(self, name: str) -> Optional[BaseProvider]:
        """Get provider by name"""
        return self.providers.get(name)
    
    async def generate_from_provider(self, provider_name: str, prompt: str, **kwargs) -> Dict[str, Any]:
        """Generate response from specific provider"""
        provider = self.get_provider(provider_name)
        if not provider:
            return {
                "provider": provider_name,
                "status": "error",
                "error": "Provider not found"
            }
        
        try:
            # Add timeout
            result = await asyncio.wait_for(
                provider.generate(prompt, **kwargs),
                timeout=self.timeout_seconds
            )
            result["status"] = "success"
            return result
            
        except asyncio.TimeoutError:
            logger.warning(f"Provider {provider_name} timed out")
            return {
                "provider": provider_name,
                "status": "timeout",
                "error": f"Request timed out after {self.timeout_seconds} seconds"
            }
        except Exception as e:
            logger.error(f"Provider {provider_name} error: {str(e)}")
            return {
                "provider": provider_name,
                "status": "error",
                "error": str(e)
            }
    
    async def generate_from_all(self, prompt: str, **kwargs) -> List[Dict[str, Any]]:
        """Generate responses from all available providers"""
        tasks = []
        for provider_name in self.providers.keys():
            task = self.generate_from_provider(provider_name, prompt, **kwargs)
            tasks.append(task)
        
        if not tasks:
            return []
        
        # Run all providers concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter out exceptions and format results
        formatted_results = []
        for result in results:
            if isinstance(result, dict):
                formatted_results.append(result)
            else:
                # Exception occurred
                logger.error(f"Provider exception: {result}")
        
        return formatted_results
    
    async def get_all_health_status(self) -> Dict[str, Dict[str, Any]]:
        """Get health status for all providers"""
        health_results = {}
        
        for name, provider in self.providers.items():
            try:
                health_results[name] = await provider.health_check()
            except Exception as e:
                health_results[name] = {
                    "provider": name,
                    "status": "error", 
                    "configured": bool(provider.api_key),
                    "reachable": False,
                    "error": str(e)
                }
        
        return health_results