"""
COM-AI v3 - Base Memory Interface
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

class BaseMemory(ABC):
    """Abstract base class for memory systems"""
    
    @abstractmethod
    async def store(self, key: str, value: Any) -> bool:
        """Store a value in memory"""
        pass
    
    @abstractmethod
    async def retrieve(self, key: str) -> Optional[Any]:
        """Retrieve a value from memory"""
        pass
    
    @abstractmethod
    async def delete(self, key: str) -> bool:
        """Delete a value from memory"""
        pass
    
    @abstractmethod
    def get_health(self) -> Dict[str, Any]:
        """Get memory system health status"""
        pass