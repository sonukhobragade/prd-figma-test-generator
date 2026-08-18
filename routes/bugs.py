"""
Bugs Knowledge routes.

Upload bug CSVs to RAG so test generator learns from historical bugs
and generates tests that catch similar issues.
"""

import logging
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/bugs", tags=["Bugs Knowledge"])


def get_bugs_rag():
    """Get BugsRAG instance with lazy initialization."""
    try:
        from rag.bugs_rag import BugsRAG
        return BugsRAG()
    except Exception as e:
        logger.error(f"Failed to initialize BugsRAG: {e}")
        return None


@router.get("/status")
async def get_bugs_status():
    """Get bugs knowledge system status.

    Returns:
        JSON with bugs RAG health status and statistics.
    """
    bugs_rag = get_bugs_rag()

    if bugs_rag is None:
        return JSONResponse(content={
            "enabled": False,
            "health": "offline",
            "message": "Bugs RAG system unavailable. Qdrant may not be running.",
            "total_bugs": 0,
            "by_feature": {},
        })

    try:
        stats = bugs_rag.get_stats()
        by_feature = bugs_rag.get_bugs_by_feature()

        return JSONResponse(content={
            "enabled": True,
            "health": "healthy",
            "total_bugs": stats.get("total_bugs", 0),
            "by_feature": by_feature,
        })
    except Exception as e:
        logger.error(f"Error getting bugs status: {e}")
        return JSONResponse(content={
            "enabled": False,
            "health": "error",
            "message": str(e),
            "total_bugs": 0,
            "by_feature": {},
        })


@router.post("/upload")
async def upload_bugs_csv(
    file: UploadFile = File(...),
    feature_name: str = Form(...),
):
    """Upload a bugs CSV file and index to RAG.

    The system auto-detects the CSV format and normalizes it for indexing.

    Supported formats:
    - Frontend Bugs: Bugs, Dev, Priority, Dev Status, QA Status, Comments
    - UI/Visual Bugs: #, Bugs, Priority, Dev Status, QA Status, Comments
    - API/Backend: Test Suite, TC, Test Description, Actual Result, Expected Result, Status, Root Cause...
    - Navigation Truth Table: Screen, CheckPoint, Failed (Redirected To), ...

    Args:
        file: CSV file to upload
        feature_name: Feature name for grouping (e.g., "Subscription Flow")

    Returns:
        Upload stats including bug count, format detected, and priority breakdown.
    """
    bugs_rag = get_bugs_rag()

    if bugs_rag is None:
        raise HTTPException(
            status_code=503,
            detail="Bugs RAG system unavailable. Ensure Qdrant is running."
        )

    try:
        # Get filename
        source_file = file.filename or "unknown.csv"

        # Check for duplicate file
        duplicate_check = bugs_rag.check_duplicate_file(source_file)
        if duplicate_check.get("exists"):
            return JSONResponse(
                status_code=409,
                content={
                    "success": False,
                    "message": f"CSV '{source_file}' has already been uploaded with {duplicate_check.get('bug_count', 0)} bugs for feature '{duplicate_check.get('feature_name', 'Unknown')}'",
                    "duplicate": True,
                    "source_file": source_file,
                    "existing_bug_count": duplicate_check.get("bug_count", 0),
                    "existing_feature": duplicate_check.get("feature_name", "Unknown"),
                }
            )

        # Read file content
        content = await file.read()
        csv_content = content.decode("utf-8")

        # Parse CSV
        from framework.bugs_parser import parse_bugs_csv

        bugs, stats = parse_bugs_csv(csv_content, feature_name, source_file)

        if not bugs:
            return JSONResponse(content={
                "success": False,
                "message": "No bugs found in CSV. Check the format.",
                "format_detected": stats.get("format", "unknown"),
                "total": 0,
            })

        # Store in RAG
        bugs_rag.store_bugs(bugs)

        return JSONResponse(content={
            "success": True,
            "message": f"Successfully indexed {len(bugs)} bugs from {source_file}",
            "feature_name": feature_name,
            "source_file": source_file,
            "format_detected": stats.get("format", "unknown"),
            "total": stats.get("total", 0),
            "p0": stats.get("p0", 0),
            "p1": stats.get("p1", 0),
            "p2": stats.get("p2", 0),
            "by_category": stats.get("by_category", {}),
            "by_status": stats.get("by_status", {}),
        })

    except UnicodeDecodeError:
        raise HTTPException(
            status_code=400,
            detail="Could not decode CSV file. Ensure it's UTF-8 encoded."
        )
    except Exception as e:
        logger.error(f"Error uploading bugs CSV: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/preview")
async def preview_bugs_csv(
    file: UploadFile = File(...),
    feature_name: str = Form(...),
):
    """Preview bugs CSV parsing without indexing.

    Use this to verify format detection and parsed data before uploading.

    Args:
        file: CSV file to preview
        feature_name: Feature name for grouping

    Returns:
        Parsed bugs preview with stats (not indexed).
    """
    try:
        # Read file content
        content = await file.read()
        csv_content = content.decode("utf-8")

        # Get filename
        source_file = file.filename or "unknown.csv"

        # Parse CSV
        from framework.bugs_parser import parse_bugs_csv

        bugs, stats = parse_bugs_csv(csv_content, feature_name, source_file)

        # Return preview (first 10 bugs)
        preview_bugs = [bug.to_dict() for bug in bugs[:10]]

        return JSONResponse(content={
            "success": True,
            "preview": True,
            "feature_name": feature_name,
            "source_file": source_file,
            "format_detected": stats.get("format", "unknown"),
            "total": stats.get("total", 0),
            "p0": stats.get("p0", 0),
            "p1": stats.get("p1", 0),
            "p2": stats.get("p2", 0),
            "by_category": stats.get("by_category", {}),
            "by_status": stats.get("by_status", {}),
            "bugs_preview": preview_bugs,
        })

    except UnicodeDecodeError:
        raise HTTPException(
            status_code=400,
            detail="Could not decode CSV file. Ensure it's UTF-8 encoded."
        )
    except Exception as e:
        logger.error(f"Error previewing bugs CSV: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/list")
async def list_bugs(
    feature_name: Optional[str] = None,
    source_file: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
):
    """List all bugs with optional filters.

    Args:
        feature_name: Filter by feature name
        source_file: Filter by source CSV file
        limit: Max bugs to return (default 100)
        offset: Pagination offset

    Returns:
        List of bug documents with metadata.
    """
    bugs_rag = get_bugs_rag()

    if bugs_rag is None:
        return JSONResponse(content={
            "success": False,
            "message": "Bugs RAG system unavailable",
            "bugs": [],
            "total": 0,
        })

    try:
        bugs = bugs_rag.get_all_bugs(
            feature_name=feature_name,
            source_file=source_file,
            limit=limit,
            offset=offset,
        )

        return JSONResponse(content={
            "success": True,
            "bugs": bugs,
            "returned": len(bugs),
            "limit": limit,
            "offset": offset,
            "filters": {
                "feature_name": feature_name,
                "source_file": source_file,
            }
        })

    except Exception as e:
        logger.error(f"Error listing bugs: {e}")
        return JSONResponse(content={
            "success": False,
            "message": str(e),
            "bugs": [],
            "total": 0,
        })


@router.get("/search")
async def search_bugs(
    q: str,
    feature_name: Optional[str] = None,
    priority: Optional[str] = None,
    category: Optional[str] = None,
    top_k: int = 10,
):
    """Semantic search for bugs.

    Args:
        q: Search query (e.g., "subscription payment")
        feature_name: Filter by feature name
        priority: Filter by priority (P0, P1, P2)
        category: Filter by category
        top_k: Number of results (default 10)

    Returns:
        List of matching bugs with relevance scores.
    """
    bugs_rag = get_bugs_rag()

    if bugs_rag is None:
        return JSONResponse(content={
            "success": False,
            "message": "Bugs RAG system unavailable",
            "results": [],
        })

    try:
        results = bugs_rag.search_bugs(
            query=q,
            top_k=top_k,
            feature_name=feature_name,
            priority=priority,
            category=category,
        )

        return JSONResponse(content={
            "success": True,
            "query": q,
            "results": results,
            "count": len(results),
            "filters": {
                "feature_name": feature_name,
                "priority": priority,
                "category": category,
            }
        })

    except Exception as e:
        logger.error(f"Error searching bugs: {e}")
        return JSONResponse(content={
            "success": False,
            "message": str(e),
            "results": [],
        })


@router.get("/by-feature")
async def get_bugs_by_feature():
    """Get bug statistics grouped by feature.

    Returns:
        Dict mapping feature names to bug counts and priority breakdown.
    """
    bugs_rag = get_bugs_rag()

    if bugs_rag is None:
        return JSONResponse(content={
            "success": False,
            "message": "Bugs RAG system unavailable",
            "features": {},
        })

    try:
        by_feature = bugs_rag.get_bugs_by_feature()

        # Sort by total count
        sorted_features = dict(
            sorted(
                by_feature.items(),
                key=lambda x: x[1].get("total", 0),
                reverse=True
            )
        )

        return JSONResponse(content={
            "success": True,
            "features": sorted_features,
            "total_features": len(sorted_features),
        })

    except Exception as e:
        logger.error(f"Error getting bugs by feature: {e}")
        return JSONResponse(content={
            "success": False,
            "message": str(e),
            "features": {},
        })


@router.get("/context/{feature}")
async def get_bugs_context(
    feature: str,
    top_k: int = 8,
):
    """Get bugs context for test generation.

    This endpoint returns formatted bug context that can be included
    in the test generation prompt.

    Args:
        feature: Feature name or description
        top_k: Number of bugs to include (default 8)

    Returns:
        Formatted context string for LLM prompt.
    """
    bugs_rag = get_bugs_rag()

    if bugs_rag is None:
        return JSONResponse(content={
            "success": False,
            "message": "Bugs RAG system unavailable",
            "context": "",
        })

    try:
        context = bugs_rag.get_bugs_context(feature, top_k=top_k)

        return JSONResponse(content={
            "success": True,
            "feature": feature,
            "context": context,
            "context_length": len(context),
        })

    except Exception as e:
        logger.error(f"Error getting bugs context: {e}")
        return JSONResponse(content={
            "success": False,
            "message": str(e),
            "context": "",
        })


@router.delete("/file/{source_file}")
async def delete_bugs_by_file(source_file: str):
    """Delete all bugs from a specific source file.

    Args:
        source_file: The source CSV filename to delete

    Returns:
        Deletion status.
    """
    bugs_rag = get_bugs_rag()

    if bugs_rag is None:
        raise HTTPException(
            status_code=503,
            detail="Bugs RAG system unavailable"
        )

    try:
        result = bugs_rag.delete_bugs_by_file(source_file)

        if result.get("status") == "success":
            return JSONResponse(content={
                "success": True,
                "message": f"Deleted all bugs from {source_file}",
                "deleted_file": source_file,
            })
        else:
            raise HTTPException(
                status_code=500,
                detail=result.get("error", "Unknown error")
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting bugs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/clear-all")
async def clear_all_bugs():
    """Clear all bugs from the knowledge base.

    WARNING: This deletes ALL bug data. Use with caution.

    Returns:
        Deletion status.
    """
    bugs_rag = get_bugs_rag()

    if bugs_rag is None:
        raise HTTPException(
            status_code=503,
            detail="Bugs RAG system unavailable"
        )

    try:
        result = bugs_rag.clear_all()

        if result.get("status") == "success":
            return JSONResponse(content={
                "success": True,
                "message": "All bugs cleared from knowledge base",
            })
        else:
            raise HTTPException(
                status_code=500,
                detail=result.get("error", "Unknown error")
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error clearing bugs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analyze")
async def analyze_bugs_for_rules():
    """Analyze all bugs to extract business rules and patterns.

    Returns:
        Analysis results including extracted rules, patterns, and suggestions.
    """
    bugs_rag = get_bugs_rag()

    if bugs_rag is None:
        raise HTTPException(
            status_code=503,
            detail="Bugs RAG system unavailable"
        )

    try:
        # Get all bugs
        bugs = bugs_rag.get_all_bugs(limit=1000)

        if not bugs:
            return JSONResponse(content={
                "success": True,
                "message": "No bugs to analyze",
                "total_bugs": 0,
                "extracted_rules": 0,
                "rules": [],
            })

        # Analyze bugs
        from framework.bugs_analyzer import BugsAnalyzer

        analyzer = BugsAnalyzer()
        analysis = analyzer.analyze_bugs(bugs)

        # Get domain knowledge suggestions
        suggestions = analyzer.get_domain_knowledge_suggestions()

        return JSONResponse(content={
            "success": True,
            "total_bugs": analysis.get("total_bugs", 0),
            "bugs_by_category": analysis.get("bugs_by_category", {}),
            "bugs_by_priority": analysis.get("bugs_by_priority", {}),
            "extracted_rules": analysis.get("extracted_rules", 0),
            "rules": analysis.get("rules", []),
            "patterns": analysis.get("patterns", {}),
            "suggestions": [
                {
                    "section": s.section,
                    "content": s.content,
                    "priority": s.priority,
                }
                for s in suggestions
            ],
        })

    except Exception as e:
        logger.error(f"Error analyzing bugs: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/domain-knowledge/suggestions")
async def get_domain_knowledge_suggestions():
    """Get suggestions for updating domain knowledge based on bug patterns.

    Returns:
        List of suggested updates organized by section.
    """
    bugs_rag = get_bugs_rag()

    if bugs_rag is None:
        raise HTTPException(
            status_code=503,
            detail="Bugs RAG system unavailable"
        )

    try:
        # Get all bugs
        bugs = bugs_rag.get_all_bugs(limit=1000)

        if not bugs:
            return JSONResponse(content={
                "success": True,
                "suggestions": [],
                "message": "No bugs to analyze",
            })

        # Analyze and get suggestions
        from framework.bugs_analyzer import BugsAnalyzer

        analyzer = BugsAnalyzer()
        analyzer.analyze_bugs(bugs)
        suggestions = analyzer.get_domain_knowledge_suggestions()

        # Also generate markdown
        markdown = analyzer.generate_markdown_update()

        return JSONResponse(content={
            "success": True,
            "suggestions": [
                {
                    "section": s.section,
                    "content": s.content,
                    "source_rules": s.source_rules,
                    "priority": s.priority,
                    "created_at": s.created_at,
                }
                for s in suggestions
            ],
            "markdown": markdown,
            "total_rules": len(analyzer.extracted_rules),
        })

    except Exception as e:
        logger.error(f"Error getting suggestions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/domain-knowledge/update")
async def update_domain_knowledge():
    """Auto-update domain knowledge file with extracted business rules.

    Creates or updates docs/knowledge_base/bugs_learned_rules.md

    Returns:
        Status of the update operation.
    """
    bugs_rag = get_bugs_rag()

    if bugs_rag is None:
        raise HTTPException(
            status_code=503,
            detail="Bugs RAG system unavailable"
        )

    try:
        # Get all bugs
        bugs = bugs_rag.get_all_bugs(limit=1000)

        if not bugs:
            return JSONResponse(content={
                "success": False,
                "message": "No bugs to analyze",
            })

        # Analyze and generate markdown
        from framework.bugs_analyzer import BugsAnalyzer
        import os

        analyzer = BugsAnalyzer()
        analyzer.analyze_bugs(bugs)
        markdown = analyzer.generate_markdown_update()

        # Write to file
        output_dir = "docs/knowledge_base"
        os.makedirs(output_dir, exist_ok=True)

        output_path = os.path.join(output_dir, "bugs_learned_rules.md")
        with open(output_path, "w") as f:
            f.write(markdown)

        return JSONResponse(content={
            "success": True,
            "message": f"Updated {output_path}",
            "file_path": output_path,
            "total_rules": len(analyzer.extracted_rules),
            "categories": list(set(r.category for r in analyzer.extracted_rules)),
        })

    except Exception as e:
        logger.error(f"Error updating domain knowledge: {e}")
        raise HTTPException(status_code=500, detail=str(e))
