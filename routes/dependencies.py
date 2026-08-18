"""Shared dependencies and configuration for all routes."""

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from pydantic import BaseModel

# Initialize logger
logger = logging.getLogger(__name__)

# =============================================================================
# Directory Configuration
# =============================================================================

OUTPUT_DIR = Path(os.getenv("OUTPUT_STORAGE_PATH", "output"))
PRD_STORAGE_DIR = Path(os.getenv("PRD_STORAGE_PATH", "prd"))
FEATURES_DIR = Path(os.getenv("FEATURES_STORAGE_PATH", "features"))

# Ensure directories exist
OUTPUT_DIR.mkdir(exist_ok=True)
PRD_STORAGE_DIR.mkdir(exist_ok=True)
FEATURES_DIR.mkdir(exist_ok=True)

# =============================================================================
# Qdrant Configuration
# =============================================================================

QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6335"))

# =============================================================================
# Pydantic Models for API Requests/Responses
# =============================================================================


class AnalysisResponse(BaseModel):
    """Response model for PRD/Figma analysis."""

    feature_name: str
    test_points: List[dict]
    coverage_score: float
    checklist_path: str
    testcases_path: str
    generated_at: str


class RAGStatusResponse(BaseModel):
    """Response model for RAG status."""

    enabled: bool
    qdrant_connected: bool
    indexed_sessions: int
    total_test_cases: int
    message: str


class FeatureResponse(BaseModel):
    """Response model for feature operations."""

    id: str
    name: str
    keywords: List[str]
    description: str
    prd_count: int
    figma_count: int
    created_at: str
    updated_at: str


class FeatureCreateRequest(BaseModel):
    """Request model for creating a feature."""

    name: str
    keywords: Optional[List[str]] = []
    description: Optional[str] = ""


class FeatureUpdateRequest(BaseModel):
    """Request model for updating a feature."""

    name: Optional[str] = None
    keywords: Optional[List[str]] = None
    description: Optional[str] = None


# =============================================================================
# RAG Integration Singleton
# =============================================================================

from framework.rag_integration import TestCaseRAG  # noqa: E402  (needs the path/env setup above)

_rag_integration: Optional[TestCaseRAG] = None


def get_rag() -> Optional[TestCaseRAG]:
    """Get or initialize RAG integration (singleton pattern)."""
    global _rag_integration
    if _rag_integration is None:
        try:
            _rag_integration = TestCaseRAG(qdrant_port=QDRANT_PORT)
            if _rag_integration.enabled:
                logger.info("RAG integration initialized successfully")
            else:
                logger.warning("RAG integration disabled (Qdrant unavailable)")
        except Exception as e:
            logger.error(f"Failed to initialize RAG: {e}")
            _rag_integration = None
    return _rag_integration


# =============================================================================
# Background Task Helpers
# =============================================================================


async def index_session_background(
    test_cases: List,
    checklist,
    prd_content: str,
    session_id: str,
    # VERSION TRACKING PARAMS
    version: int = 1,
    documents_included: Optional[List[str]] = None,
    source_document: str = "prd",
    test_scope: str = "frontend",
) -> None:
    """Background task to index test cases in RAG.

    Args:
        test_cases: List of generated test cases.
        checklist: The test checklist.
        prd_content: Original PRD content.
        session_id: Unique session identifier (format: FeatureName_V1).
        version: Version number.
        documents_included: List of source documents (e.g., ["prd", "frontend_lld"]).
        source_document: Which document generated these tests.
        test_scope: "frontend" or "backend".
    """
    try:
        rag = get_rag()
        if rag and rag.enabled:
            # Index the session with version metadata
            await rag.index_session(
                test_cases=test_cases,
                checklist=checklist,
                prd_content=prd_content,
                session_id=session_id,
                version=version,
                documents_included=documents_included or ["prd"],
                source_document=source_document,
                test_scope=test_scope,
            )
            logger.info(f"Indexed {len(test_cases)} test cases for session {session_id} (v{version})")
    except Exception as e:
        logger.error(f"Failed to index session {session_id}: {e}")


# =============================================================================
# Utility Functions
# =============================================================================


def get_timestamp() -> str:
    """Get current timestamp in standard format."""
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def get_iso_timestamp() -> str:
    """Get current timestamp in ISO format."""
    return datetime.now().isoformat()
