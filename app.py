#!/usr/bin/env python3
"""FastAPI web application for PRD Test Case Generator.

This is the main application entry point. All route handlers are organized
in the routes/ directory for better maintainability:

- routes/core.py - Root, download, history endpoints
- routes/prd.py - PRD analysis (streaming and non-streaming)
- routes/figma.py - Figma analysis (streaming and non-streaming)
- routes/screenshot.py - Screenshot analysis (streaming)
- routes/backend.py - Backend test generation (streaming)
- routes/rag.py - RAG (Retrieval Augmented Generation) endpoints
- routes/zk.py - ZooKeeper config sync endpoints
- routes/features.py - Feature management endpoints
"""

import logging
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from framework.utils import load_environment, setup_logging

# Import all routers
from routes import (
    core_router,
    prd_router,
    figma_router,
    screenshot_router,
    backend_router,
    rag_router,
    zk_router,
    features_router,
    bugs_router,
)

# =============================================================================
# Logging and Environment Setup
# =============================================================================

setup_logging()
load_environment()

logger = logging.getLogger(__name__)

# =============================================================================
# Application Configuration
# =============================================================================

APP_NAME = os.getenv("APP_NAME", "prd-test-generator")
APP_VERSION = os.getenv("APP_VERSION", "2.0.0")
APP_ENV = os.getenv("APP_ENV", "development")
DEBUG = os.getenv("DEBUG", "true").lower() == "true"

# CORS configuration
CORS_ENABLED = os.getenv("CORS_ENABLED", "true").lower() == "true"
CORS_ORIGINS = (
    os.getenv("CORS_ORIGINS", "*").split(",") if os.getenv("CORS_ORIGINS") else ["*"]
)

# =============================================================================
# Directory Configuration
# =============================================================================

OUTPUT_DIR = Path(os.getenv("OUTPUT_STORAGE_PATH", "output"))
PRD_STORAGE_DIR = Path(os.getenv("PRD_STORAGE_PATH", "prd"))
FRONTEND_DIST = Path("frontend/dist")

# Ensure directories exist
OUTPUT_DIR.mkdir(exist_ok=True)
PRD_STORAGE_DIR.mkdir(exist_ok=True)

# =============================================================================
# FastAPI Application
# =============================================================================

app = FastAPI(
    title=APP_NAME.replace("-", " ").title(),
    version=APP_VERSION,
    debug=DEBUG,
    description="PRD & Figma Test Case Generator API - Generate comprehensive test cases from PRD documents and Figma designs.",
    docs_url="/docs",
    redoc_url="/redoc",
)

# =============================================================================
# Middleware
# =============================================================================

if CORS_ENABLED:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    logger.info(f"CORS enabled with origins: {CORS_ORIGINS}")

# =============================================================================
# Static Files
# =============================================================================

# Mount output directory for generated files
app.mount("/output", StaticFiles(directory=str(OUTPUT_DIR)), name="output")

# Mount static files from frontend build (if exists)
if FRONTEND_DIST.exists():
    if (FRONTEND_DIST / "assets").exists():
        app.mount(
            "/assets",
            StaticFiles(directory=str(FRONTEND_DIST / "assets")),
            name="assets",
        )
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIST)), name="static")

# =============================================================================
# Include Routers
# =============================================================================

# Core routes (root, download, history)
app.include_router(core_router)

# Analysis routes
app.include_router(prd_router)
app.include_router(figma_router)
app.include_router(screenshot_router)
app.include_router(backend_router)

# RAG and knowledge management
app.include_router(rag_router)
app.include_router(zk_router)
app.include_router(bugs_router)

# Feature management
app.include_router(features_router)

# =============================================================================
# Startup/Shutdown Events
# =============================================================================

@app.on_event("startup")
async def startup_event():
    """Application startup handler."""
    logger.info(f"Starting {APP_NAME} v{APP_VERSION} in {APP_ENV} mode")
    logger.info(f"Output directory: {OUTPUT_DIR}")
    logger.info(f"PRD storage directory: {PRD_STORAGE_DIR}")

    # Log API key availability (for debugging)
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")
    figma_token = os.getenv("FIGMA_API_TOKEN")

    if not anthropic_key and not openai_key:
        logger.warning("No API keys found in environment. Users must provide their own API key.")
    else:
        logger.info(f"API keys configured: Anthropic={bool(anthropic_key)}, OpenAI={bool(openai_key)}")

    if figma_token:
        logger.info("Figma API token configured")
    else:
        logger.warning("Figma API token not configured")


@app.on_event("shutdown")
async def shutdown_event():
    """Application shutdown handler."""
    logger.info(f"Shutting down {APP_NAME}")


# =============================================================================
# Main Entry Point
# =============================================================================

if __name__ == "__main__":
    import uvicorn

    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))

    uvicorn.run(
        "app:app",
        host=host,
        port=port,
        reload=DEBUG,
        log_level="debug" if DEBUG else "info",
    )
