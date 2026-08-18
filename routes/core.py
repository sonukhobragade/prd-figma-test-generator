"""Core routes - root, downloads, history."""

import logging
import os
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, HTMLResponse

from routes.dependencies import OUTPUT_DIR

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Core"])

# Frontend build directory
FRONTEND_DIST = Path("frontend/dist")


@router.get("/", response_class=HTMLResponse)
async def root():
    """Serve the frontend or show API info."""
    index_path = FRONTEND_DIST / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return """
    <html>
        <head>
            <title>PRD Test Generator API</title>
            <style>
                body { font-family: system-ui, sans-serif; max-width: 800px; margin: 50px auto; padding: 20px; }
                h1 { color: #333; }
                .endpoint { background: #f5f5f5; padding: 10px; margin: 10px 0; border-radius: 5px; }
                code { background: #e0e0e0; padding: 2px 6px; border-radius: 3px; }
            </style>
        </head>
        <body>
            <h1>PRD Test Generator API</h1>
            <p>Welcome to the PRD to Test Case Generator API.</p>
            <h2>Endpoints</h2>
            <div class="endpoint"><code>POST /api/analyze-prd</code> - Analyze PRD document</div>
            <div class="endpoint"><code>POST /api/analyze-figma</code> - Analyze Figma design</div>
            <div class="endpoint"><code>POST /api/analyze-prd-stream</code> - Stream PRD analysis</div>
            <div class="endpoint"><code>POST /api/analyze-figma-stream</code> - Stream Figma analysis</div>
            <div class="endpoint"><code>POST /api/analyze-prd-backend-stream</code> - Stream Backend test generation</div>
            <div class="endpoint"><code>GET /api/history</code> - Get analysis history</div>
            <div class="endpoint"><code>GET /api/rag/status</code> - Get RAG status</div>
            <p>For full documentation, visit <a href="/docs">/docs</a></p>
        </body>
    </html>
    """


@router.get("/api/download/{file_type}/{filename}")
async def download_file(file_type: str, filename: str):
    """Download generated files (checklist or testcases).

    Args:
        file_type: Type of file ('checklist' or 'testcases').
        filename: Name of the file to download.

    Returns:
        FileResponse with the requested file.
    """
    if file_type not in ["checklist", "testcases", "truth_table", "backend_testcases"]:
        raise HTTPException(status_code=400, detail="Invalid file type")

    file_path = OUTPUT_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    media_type = "text/markdown" if filename.endswith(".md") else "text/csv"
    return FileResponse(
        path=file_path,
        filename=filename,
        media_type=media_type,
    )


@router.get("/api/history")
async def get_history():
    """Get list of previously generated test files.

    Returns:
        List of generated files with metadata.
    """
    history = []

    if OUTPUT_DIR.exists():
        for file_path in sorted(OUTPUT_DIR.glob("*"), key=os.path.getmtime, reverse=True):
            if file_path.is_file():
                stat = file_path.stat()
                history.append({
                    "filename": file_path.name,
                    "type": "checklist" if file_path.suffix == ".md" else "testcases",
                    "size": stat.st_size,
                    "created_at": stat.st_mtime,
                    "download_url": f"/api/download/{'checklist' if file_path.suffix == '.md' else 'testcases'}/{file_path.name}",
                })

    return {"history": history[:50]}  # Limit to 50 most recent


@router.delete("/api/clear-history")
async def clear_history():
    """Clear all generated files from history.

    Returns:
        Success message with count of deleted files.
    """
    deleted_count = 0

    if OUTPUT_DIR.exists():
        for file_path in OUTPUT_DIR.glob("*"):
            if file_path.is_file():
                try:
                    file_path.unlink()
                    deleted_count += 1
                except Exception as e:
                    logger.error(f"Failed to delete {file_path}: {e}")

    return {"message": f"Deleted {deleted_count} files", "deleted_count": deleted_count}
