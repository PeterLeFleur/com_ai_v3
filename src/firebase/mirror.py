"""
Firebase mirroring logic - fire-and-forget writes to Firestore.
PostgreSQL is authoritative; Firestore failures MUST NOT block API responses.
"""

import logging
import time
from datetime import datetime
from typing import Optional, Dict, Any
from uuid import UUID

from google.cloud.firestore import AsyncClient

logger = logging.getLogger(__name__)


class FirestoreMirror:
    """Handles all Firestore mirroring operations with comprehensive debugging"""
    
    def __init__(self, db: AsyncClient, enable_debug: bool = False):
        self.db = db
        self.enable_debug = enable_debug
        self._mirror_stats = {
            "success": 0,
            "failures": 0,
            "last_error": None,
            "last_error_time": None
        }
    
    def get_stats(self) -> dict:
        """Return mirroring statistics for diagnostics"""
        return self._mirror_stats.copy()
    
    async def _safe_write(
        self, 
        collection: str, 
        doc_id: str, 
        data: Dict[str, Any],
        context: Optional[str] = None
    ) -> bool:
        """
        Safe write with detailed error logging and timing.
        Returns True if successful, False otherwise.
        """
        start_time = time.time()
        
        try:
            # Log attempt if debug enabled
            if self.enable_debug:
                logger.debug(
                    f"Firestore mirror attempt: {collection}/{doc_id}",
                    extra={
                        "collection": collection,
                        "doc_id": doc_id,
                        "data_keys": list(data.keys()),
                        "context": context
                    }
                )
            
            doc_ref = self.db.collection(collection).document(doc_id)
            await doc_ref.set(data)
            
            elapsed_ms = (time.time() - start_time) * 1000
            
            # Log success with timing
            logger.info(
                f"Firestore mirror success: {collection}/{doc_id} ({elapsed_ms:.1f}ms)",
                extra={
                    "collection": collection,
                    "doc_id": doc_id,
                    "latency_ms": elapsed_ms,
                    "context": context
                }
            )
            
            self._mirror_stats["success"] += 1
            return True
            
        except Exception as e:
            elapsed_ms = (time.time() - start_time) * 1000
            
            # Detailed error logging
            error_info = {
                "collection": collection,
                "doc_id": doc_id,
                "error_type": type(e).__name__,
                "error_message": str(e),
                "latency_ms": elapsed_ms,
                "context": context,
                "data_preview": {k: str(v)[:50] for k, v in list(data.items())[:3]}
            }
            
            logger.error(
                f"Firestore mirror failed: {collection}/{doc_id} - {e}",
                extra=error_info,
                exc_info=True
            )
            
            # Track failure stats
            self._mirror_stats["failures"] += 1
            self._mirror_stats["last_error"] = str(e)
            self._mirror_stats["last_error_time"] = time.time()
            
            return False
    
    def _serialize_datetime(self, dt: Optional[datetime]) -> Optional[str]:
        """Convert datetime to ISO string for Firestore"""
        return dt.isoformat() if dt else None
    
    def _serialize_uuid(self, uuid_val: Optional[UUID]) -> Optional[str]:
        """Convert UUID to string for Firestore"""
        return str(uuid_val) if uuid_val else None
    
    async def mirror_user(self, user, context: str = "unknown") -> bool:
        """Mirror User model to Firestore"""
        data = {
            "id": self._serialize_uuid(user.id),
            "external_id": user.external_id,
            "role": user.role,
            "created_at": self._serialize_datetime(user.created_at)
        }
        return await self._safe_write("users", str(user.id), data, context)
    
    async def mirror_session(self, session, context: str = "unknown") -> bool:
        """Mirror Session model to Firestore"""
        data = {
            "id": self._serialize_uuid(session.id),
            "user_id": self._serialize_uuid(session.user_id),
            "title": session.title,
            "session_metadata": session.session_metadata or {},
            "started_at": self._serialize_datetime(session.started_at),
            "last_active_at": self._serialize_datetime(session.last_active_at)
        }
        return await self._safe_write("sessions", str(session.id), data, context)
    
    async def mirror_message(self, message, context: str = "unknown") -> bool:
        """Mirror Message model to Firestore"""
        data = {
            "id": self._serialize_uuid(message.id),
            "session_id": self._serialize_uuid(message.session_id),
            "role": message.role,
            "content": message.content,
            "provider": message.provider,
            "model": message.model,
            "tokens_in": message.tokens_in,
            "tokens_out": message.tokens_out,
            "latency_ms": message.latency_ms,
            "request_id": self._serialize_uuid(message.request_id),
            "created_at": self._serialize_datetime(message.created_at)
        }
        return await self._safe_write("messages", str(message.id), data, context)
    
    async def mirror_usage_log(self, usage_log, context: str = "unknown") -> bool:
        """
        Mirror UsageLog model to Firestore.
        CRITICAL: Includes fallback_chain with Phase 2A contract structure.
        """
        fallback_chain = usage_log.fallback_chain or {}
        
        data = {
            "request_id": self._serialize_uuid(usage_log.request_id),
            "user_id": self._serialize_uuid(usage_log.user_id),
            "provider": usage_log.provider,
            "model": usage_log.model,
            "status": usage_log.status,
            "tokens_in": usage_log.tokens_in,
            "tokens_out": usage_log.tokens_out,
            "latency_ms": usage_log.latency_ms,
            "cost_usd": usage_log.cost_usd,
            "fallback_chain": {
                "strategy": fallback_chain.get("strategy", "unknown"),
                "attempts": fallback_chain.get("attempts", []),
                "winner": fallback_chain.get("winner"),
                "latency_ms_total": fallback_chain.get("latency_ms_total", 0)
            },
            "created_at": self._serialize_datetime(usage_log.created_at)
        }
        
        return await self._safe_write(
            "usage_log", 
            str(usage_log.request_id), 
            data, 
            context
        )