"""
COM-AI v3 - Provider Management Routes
"""

from fastapi import APIRouter

router = APIRouter()

@router.get("/providers")
async def list_providers():
    """List available AI providers"""
    return {
        "providers": [],
        "total": 0,
        "status": "not_implemented"
    }