"""
COM-AI v3 - Health Check Routes
"""

from fastapi import APIRouter

router = APIRouter()

@router.get("/health")
async def health_check():
    """Detailed health check endpoint"""
    return {
        "status": "healthy",
        "components": {
            "api": "operational",
            "brain": "loading",
            "memory": "mock"
        }
    }