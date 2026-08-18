"""Routes package for PRD Test Case Generator API."""

from routes.core import router as core_router
from routes.prd import router as prd_router
from routes.figma import router as figma_router
from routes.screenshot import router as screenshot_router
from routes.backend import router as backend_router
from routes.rag import router as rag_router
from routes.zk import router as zk_router
from routes.features import router as features_router
from routes.bugs import router as bugs_router

__all__ = [
    "core_router",
    "prd_router",
    "figma_router",
    "screenshot_router",
    "backend_router",
    "rag_router",
    "zk_router",
    "features_router",
    "bugs_router",
]
