"""
Firebase/Firestore health check endpoint
"""

import time
import logging
from fastapi import APIRouter

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/health", tags=["health"])


@router.get("/firebase")
async def firebase_health():
    """
    Check Firestore connectivity and mirror statistics.
    Returns detailed diagnostics for troubleshooting.
    """
    result = {
        "status": "unknown",
        "connectivity": False,
        "mirror_stats": None,
        "error": None,
        "test_write": False,
        "test_read": False,
        "credentials_path": None,
        "project_id": None
    }
    
    try:
        import os
        from src.firebase.client import init_firebase
        from src.firebase.mirror import FirestoreMirror
        
        # Show credentials path for debugging
        result["credentials_path"] = os.getenv(
            "GOOGLE_APPLICATION_CREDENTIALS", 
            "firebase-credentials.json"
        )
        
        # Test client initialization
        firebase_client = init_firebase()
        result["connectivity"] = True
        result["project_id"] = firebase_client.project
        
        # Get mirror stats if available
        mirror = FirestoreMirror(firebase_client, enable_debug=True)
        result["mirror_stats"] = mirror.get_stats()
        
        # Test write
        test_doc_ref = firebase_client.collection("_health_check").document("ping")
        await test_doc_ref.set({"timestamp": time.time(), "status": "ok"})
        result["test_write"] = True
        
        # Test read
        test_doc = await test_doc_ref.get()
        result["test_read"] = test_doc.exists
        
        result["status"] = "healthy"
        
    except Exception as e:
        result["status"] = "degraded"
        result["error"] = {
            "type": type(e).__name__,
            "message": str(e)
        }
        logger.error(f"Firebase health check failed: {e}", exc_info=True)
    
    return result