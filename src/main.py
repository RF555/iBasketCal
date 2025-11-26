"""FastAPI application entry point."""

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from src.api.routes import router
from src.config import get_settings

# Configure logging
settings = get_settings()
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Israeli Basketball Calendar",
    description="Subscribable ICS calendars for Israeli basketball games",
    version="1.0.0",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(router)

# Get static files directory
static_dir = Path(__file__).parent.parent / "static"


# Serve static files if directory exists
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/")
async def serve_index():
    """Serve the main web UI."""
    index_path = static_dir / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    return {"message": "Israeli Basketball Calendar API", "docs": "/docs"}


@app.on_event("startup")
async def startup_event():
    """Application startup event handler."""
    logger.info("Starting Israeli Basketball Calendar application")
    logger.info(f"Server running on {settings.HOST}:{settings.PORT}")


@app.on_event("shutdown")
async def shutdown_event():
    """Application shutdown event handler."""
    logger.info("Shutting down Israeli Basketball Calendar application")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=True,
    )
