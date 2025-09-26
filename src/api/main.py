"""
COM-AI v3 - Basic FastAPI Application
Entry point for the API server
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.utils.config import get_settings

# Initialize FastAPI app
app = FastAPI(
    title="COM-AI v3",
    description="Multi-Provider AI Orchestration System",
    version="3.0.0"
)

# Load configuration
settings = get_settings()

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    """Root endpoint - API status"""
    return {
        "message": "COM-AI v3 API",
        "status": "operational",
        "version": "3.0.0"
    }

@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "brain_available": False,  # Will be updated when brain is implemented
        "providers": {
            "openai": "not_configured",
            "anthropic": "not_configured", 
            "gemini": "not_configured"
        },
        "memory": {
            "firestore": "not_configured",
            "postgres": "not_configured"
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.api.main:app", host="0.0.0.0", port=8000, reload=True)