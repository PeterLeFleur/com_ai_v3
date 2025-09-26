"""
COM-AI v3 - Mock Memory Implementation
"""

from typing import Dict, Any, Optional
from .base_memory import BaseMemory
import logging

logger = logging.getLogger(__name__)

class MockMemory(BaseMemory):
    """In-memory mock implementation for development"""
    
    def __init__(self):
        self.storage: Dict[str, Any] = {}
        logger.info("🧪 Mock memory initialized")
    
    async def store(self, key: str, value: Any) -> bool:
        """Store value in memory"""
        self.storage[key] = value
        logger.info(f"📝 Stored key: {key}")
        return True
    
    async def retrieve(self, key: str) -> Optional[Any]:
        """Retrieve value from memory"""
        value = self.storage.get(key)
        logger.info(f"📖 Retrieved key: {key}")
        return value
    
    async def delete(self, key: str) -> bool:
        """Delete value from memory"""
        if key in self.storage:
            del self.storage[key]
            logger.info(f"🗑️ Deleted key: {key}")
            return True
        return False
    
    def get_health(self) -> Dict[str, Any]:
        """Check mock memory health"""
        return {
            "type": "mock",
            "status": "healthy",
            "items_count": len(self.storage)
        }