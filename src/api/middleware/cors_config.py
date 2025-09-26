"""
COM-AI v3 - CORS Configuration
"""

from fastapi.middleware.cors import CORSMiddleware
from src.utils.config import get_settings

def setup_cors(app):
    """Configure CORS middleware"""
    settings = get_settings()
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )