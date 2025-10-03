"""
Firebase/Firestore schema definitions matching PostgreSQL models.py as of Oct 2, 2025.
These are reference structures - Firestore is schemaless but this documents expected fields.
"""

from typing import TypedDict, List, Optional
from datetime import datetime


class FirestoreAttempt(TypedDict):
    """Single provider attempt in fallback chain"""
    provider: str
    status: str  # "success" or "error"
    latency_ms: float
    seq: int  # attempt order
    error: Optional[str]  # if status="error"


class FirestoreFallbackChain(TypedDict):
    """Complete fallback chain for telemetry"""
    strategy: str  # "single", "fallback", or "all"
    attempts: List[FirestoreAttempt]
    winner: Optional[str]  # which provider succeeded
    latency_ms_total: float


class FirestoreUsageLog(TypedDict):
    """usage_log collection - telemetry per request"""
    request_id: str  # PRIMARY KEY (document ID)
    user_id: Optional[str]
    provider: str
    model: str
    status: str  # "ok" or "error"
    tokens_in: Optional[int]
    tokens_out: Optional[int]
    latency_ms: float
    cost_usd: Optional[float]
    fallback_chain: FirestoreFallbackChain
    created_at: datetime


class FirestoreSession(TypedDict):
    """sessions collection"""
    id: str  # document ID
    user_id: str
    title: Optional[str]
    session_metadata: dict  # NOT "metadata" - SQLAlchemy conflict
    started_at: datetime
    last_active_at: datetime


class FirestoreMessage(TypedDict):
    """messages collection"""
    id: str  # document ID
    session_id: str
    role: str  # "user" or "assistant"
    content: str
    provider: Optional[str]
    model: Optional[str]
    tokens_in: Optional[int]
    tokens_out: Optional[int]
    latency_ms: Optional[float]
    request_id: Optional[str]  # traceability to usage_log
    created_at: datetime


class FirestoreUser(TypedDict):
    """users collection"""
    id: str  # document ID
    external_id: str
    role: str
    created_at: datetime