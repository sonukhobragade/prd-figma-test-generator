"""RAG (Retrieval Augmented Generation) routes."""

import json
import logging
import os
import sys
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Form, HTTPException
from fastapi.responses import JSONResponse

from routes.dependencies import OUTPUT_DIR, get_rag

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["RAG"])

# Default codebase path - can be overridden via environment variable
CODEBASE_PATH = os.getenv(
    "REACT_NATIVE_CODEBASE_PATH",
    "/path/to/your/codebase"
)


def _derive_api_component(payload: dict) -> str:
    """Derive api_component from payload if not set."""
    api_component = payload.get("api_component", "")
    if api_component:
        return api_component

    test_type = payload.get("test_type", "")
    category = payload.get("category", "")

    if test_type == "Database":
        return "Database"
    elif test_type == "Security":
        return "Security Module"
    elif test_type == "Integration":
        return "Integration Layer"
    elif test_type == "Performance":
        return "Performance Module"
    elif test_type == "API":
        return "API Endpoint"
    elif category:
        return category.replace("-", " ").title()
    else:
        return "Backend Service"


@router.get("/rag/status")
async def get_rag_status():
    """Get RAG system status and statistics.

    Returns:
        JSON with RAG health status and indexed document counts.
    """
    rag = get_rag()

    if rag is None or not rag.enabled:
        return JSONResponse(content={
            "enabled": False,
            "health": "offline",
            "message": "RAG system unavailable. Qdrant may not be running.",
            "test_cases": {"count": 0},
            "prd_documents": {"count": 0},
            "coverage_insights": {"count": 0},
            "total_documents": 0,
        })

    stats = rag.get_rag_stats()
    return JSONResponse(content=stats)


@router.get("/rag/codebase/status")
async def get_codebase_rag_status():
    """Get codebase RAG status (React Native code knowledge).

    Returns:
        JSON with codebase RAG health, indexed files count, and last sync time.
    """
    try:
        from rag import SimpleRAG
        import requests

        # Check if Qdrant is available
        qdrant_host = os.getenv("QDRANT_HOST", "localhost")
        qdrant_port = os.getenv("QDRANT_PORT", "6335")
        qdrant_url = f"http://{qdrant_host}:{qdrant_port}"
        try:
            response = requests.get(f"{qdrant_url}/", timeout=2)
            if response.status_code != 200:
                return JSONResponse(content={
                    "enabled": False,
                    "health": "offline",
                    "message": f"Qdrant (codebase) not running on port {qdrant_port}",
                })
        except requests.exceptions.RequestException:
            return JSONResponse(content={
                "enabled": False,
                "health": "offline",
                "message": f"Qdrant (codebase) not accessible on port {qdrant_port}",
            })

        # Initialize RAG to get stats
        rag = SimpleRAG(
            collection_name="app_code",
            embedding_provider="local",
        )
        stats = rag.get_stats()

        # Load metadata if available
        metadata_path = Path(__file__).parent.parent / "lightrag_setup" / "data" / "metadata.json"
        metadata = {}
        if metadata_path.exists():
            metadata = json.loads(metadata_path.read_text())

        return JSONResponse(content={
            "enabled": True,
            "health": "healthy",
            "collection": "app_code",
            "documents": stats.get("points_count", 0),
            "codebase_path": metadata.get("codebase_path", CODEBASE_PATH),
            "file_count": metadata.get("file_count", 0),
            "chunk_count": metadata.get("chunk_count", 0),
            "last_synced": metadata.get("ingested_at", "Never"),
            "file_types": metadata.get("file_types", {}),
        })

    except Exception as e:
        logger.error(f"Error getting codebase RAG status: {e}")
        return JSONResponse(content={
            "enabled": False,
            "health": "error",
            "message": str(e),
        })


@router.post("/rag/codebase/sync")
async def sync_codebase_rag(
    codebase_path: Optional[str] = Form(None),
    force: bool = Form(False),
):
    """Sync/re-index the React Native codebase for RAG.

    Args:
        codebase_path: Path to React Native project (uses default if not provided)
        force: If True, force re-index even if data exists

    Returns:
        JSON with sync status and statistics.
    """
    try:
        # Use provided path or default
        path = codebase_path or CODEBASE_PATH

        if not Path(path).exists():
            raise HTTPException(status_code=400, detail=f"Codebase path not found: {path}")

        logger.info(f"Starting codebase sync: {path} (force={force})")

        # Import and initialize the lightrag SimpleRAG
        lightrag_path = Path(__file__).parent.parent / "lightrag_setup"
        if str(lightrag_path) not in sys.path:
            sys.path.insert(0, str(lightrag_path))

        from simple_rag import SimpleRAG as LightRAG

        # Initialize RAG
        rag = LightRAG()

        # Check if already indexed
        stats = rag.get_stats()
        if stats.get("vectors_count", 0) > 0 and not force:
            return JSONResponse(content={
                "success": True,
                "status": "skipped",
                "message": "Codebase already indexed. Use force=true to re-index.",
                "existing_documents": stats.get("vectors_count", 0),
                "codebase_path": path,
            })

        # Re-index if force=True or empty
        if force and stats.get("vectors_count", 0) > 0:
            # Clear existing data by recreating collection
            logger.info("Force sync: recreating codebase collection...")
            from qdrant_client.models import Distance, VectorParams
            try:
                rag.qdrant.delete_collection(rag.COLLECTION_NAME)
            except Exception:
                pass  # Collection might not exist
            rag.qdrant.create_collection(
                collection_name=rag.COLLECTION_NAME,
                vectors_config=VectorParams(
                    size=rag.EMBEDDING_DIM,
                    distance=Distance.COSINE
                )
            )

        # Ingest codebase
        logger.info(f"Indexing codebase: {path}")
        rag.ingest_codebase(path)

        # Get updated stats
        new_stats = rag.get_stats()

        return JSONResponse(content={
            "success": True,
            "status": "completed",
            "message": "Codebase indexed successfully",
            "codebase_path": path,
            "documents": new_stats.get("vectors_count", 0),
            "file_count": new_stats.get("file_count", 0),
            "chunk_count": new_stats.get("chunk_count", 0),
            "file_types": new_stats.get("file_types", {}),
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error syncing codebase: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/rag/projects")
async def list_projects():
    """List all projects/sessions with their test case counts.

    Returns:
        List of projects with feature breakdown.
    """
    rag = get_rag()

    if not rag or not rag.enabled:
        return JSONResponse(content={
            "success": False,
            "message": "RAG not available",
            "projects": [],
        })

    try:
        # Get all test cases to group by session
        client = rag.test_cases_rag.store.client
        collection_name = rag.test_cases_rag.store.collection_name

        all_points = []
        next_offset = None

        while True:
            result = client.scroll(
                collection_name=collection_name,
                limit=100,
                offset=next_offset,
                with_payload=True,
                with_vectors=False,
            )
            points, next_offset = result
            all_points.extend(points)
            if next_offset is None:
                break

        # Group by session_id (project)
        projects_dict = {}

        for point in all_points:
            payload = point.payload or {}
            session_id = payload.get("session_id", "unknown")
            feature_name = payload.get("feature", "Unknown")

            # Extract project name from session_id or checklist file
            project_name = session_id
            if session_id.startswith("backfill-"):
                csv_name = session_id.replace("backfill-", "")
                checklist_path = OUTPUT_DIR / f"checklist_{csv_name.replace('testcases_', '')}.md"

                if checklist_path.exists():
                    try:
                        with open(checklist_path, 'r') as f:
                            first_line = f.readline().strip()
                            if first_line.startswith("# Test Checklist:"):
                                project_name = first_line.replace("# Test Checklist:", "").strip()
                            elif first_line.startswith("#"):
                                project_name = first_line.replace("#", "").strip()
                    except Exception:
                        pass

                if project_name == session_id:
                    parts = csv_name.split("_")
                    if len(parts) >= 3:
                        if parts[1] == "figma":
                            date_str = parts[2]
                            if len(date_str) == 8:
                                project_name = f"Figma Analysis ({date_str[:4]}-{date_str[4:6]}-{date_str[6:]})"
                            else:
                                project_name = f"Figma Analysis ({date_str})"
                        else:
                            project_name = f"PRD Analysis ({parts[1]})"
            else:
                generated_at = payload.get("generated_at", "")
                if generated_at:
                    try:
                        from datetime import datetime as dt
                        date_obj = dt.fromisoformat(generated_at.replace('Z', '+00:00'))
                        date_str = date_obj.strftime("%Y-%m-%d")
                        project_name = f"{feature_name} ({date_str})"
                    except Exception:
                        project_name = feature_name or f"Analysis ({session_id[:8]}...)"
                else:
                    project_name = feature_name or f"Analysis ({session_id[:8]}...)"

            if session_id not in projects_dict:
                projects_dict[session_id] = {
                    "id": session_id,
                    "name": project_name,
                    "total_count": 0,
                    "features": {},
                    "priorities": {"P0": 0, "P1": 0, "P2": 0, "P3": 0},
                    "created_at": payload.get("generated_at", ""),
                }

            projects_dict[session_id]["total_count"] += 1
            priority = payload.get("priority", "P2")
            projects_dict[session_id]["priorities"][priority] += 1

            if feature_name not in projects_dict[session_id]["features"]:
                projects_dict[session_id]["features"][feature_name] = {
                    "name": feature_name,
                    "count": 0,
                    "priorities": {"P0": 0, "P1": 0, "P2": 0, "P3": 0},
                }
            projects_dict[session_id]["features"][feature_name]["count"] += 1
            projects_dict[session_id]["features"][feature_name]["priorities"][priority] += 1

        # Convert to list and sort features
        projects = []
        for proj in projects_dict.values():
            proj["features"] = sorted(
                proj["features"].values(),
                key=lambda x: x["count"],
                reverse=True
            )
            projects.append(proj)

        # Sort projects by total count
        projects.sort(key=lambda x: x["total_count"], reverse=True)

        return JSONResponse(content={
            "success": True,
            "projects": projects,
            "total_projects": len(projects),
        })

    except Exception as e:
        logger.error(f"Error listing projects: {e}")
        return JSONResponse(content={
            "success": False,
            "message": str(e),
            "projects": [],
        })


# ============================================================================
# Feature/Version Management Endpoints (NEW)
# ============================================================================


@router.get("/rag/features")
async def list_features():
    """List all features with their versions.

    Returns a hierarchical structure of features and their versions,
    including which documents contributed to each version.

    Returns:
        List of features with version breakdown.
    """
    rag = get_rag()

    if not rag or not rag.enabled:
        return JSONResponse(content={
            "success": False,
            "message": "RAG not available",
            "features": [],
        })

    try:
        features = rag.get_features_list()
        return JSONResponse(content={
            "success": True,
            "features": features,
            "total_features": len(features),
        })
    except Exception as e:
        logger.error(f"Error listing features: {e}")
        return JSONResponse(content={
            "success": False,
            "message": str(e),
            "features": [],
        })


@router.get("/rag/features/{feature_name}/versions")
async def get_feature_versions(feature_name: str):
    """Get all versions of a specific feature.

    Args:
        feature_name: Name of the feature.

    Returns:
        List of versions with documents and test counts.
    """
    rag = get_rag()

    if not rag or not rag.enabled:
        return JSONResponse(content={
            "success": False,
            "message": "RAG not available",
            "versions": [],
        })

    try:
        versions = rag.get_feature_versions(feature_name)
        return JSONResponse(content={
            "success": True,
            "feature_name": feature_name,
            "versions": versions,
            "total_versions": len(versions),
        })
    except Exception as e:
        logger.error(f"Error getting feature versions: {e}")
        return JSONResponse(content={
            "success": False,
            "message": str(e),
            "versions": [],
        })


@router.put("/rag/features/{feature_name}/versions/{version}")
async def update_version_documents(
    feature_name: str,
    version: int,
    documents: str = Form(...),  # Comma-separated list: "prd,frontend_lld,backend_lld"
):
    """Update the documents list for a specific version.

    Args:
        feature_name: Name of the feature.
        version: Version number.
        documents: Comma-separated list of documents.

    Returns:
        Update result.
    """
    rag = get_rag()

    if not rag or not rag.enabled:
        return JSONResponse(content={
            "success": False,
            "message": "RAG not available",
        })

    try:
        # Parse documents list
        doc_list = [d.strip() for d in documents.split(",") if d.strip()]

        # Build session_id
        feature_name_clean = feature_name.replace(" ", "_")
        session_id = f"{feature_name_clean}_V{version}"

        result = await rag.update_version_documents(session_id, doc_list)
        return JSONResponse(content={
            "success": result.get("status") == "success",
            "message": result.get("reason", "Updated successfully"),
            **result,
        })
    except Exception as e:
        logger.error(f"Error updating version documents: {e}")
        return JSONResponse(content={
            "success": False,
            "message": str(e),
        })


@router.get("/rag/test-cases")
async def list_all_test_cases(
    session_id: Optional[str] = None,
    feature: Optional[str] = None,
    test_type: Optional[str] = None,
    priority: Optional[str] = None,
    test_scope: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
):
    """List all test cases from the RAG repository.

    Args:
        session_id: Optional filter by session ID.
        feature: Optional filter by feature name.
        test_type: Optional filter by test type.
        priority: Optional filter by priority.
        test_scope: Optional filter by scope (frontend/backend).
        limit: Maximum number of results (default 100).
        offset: Pagination offset.

    Returns:
        List of test cases grouped by feature.
    """
    rag = get_rag()

    if not rag or not rag.enabled:
        return JSONResponse(content={
            "success": False,
            "message": "RAG not available",
            "test_cases": [],
            "features": [],
            "total_count": 0,
        })

    try:
        from qdrant_client.models import Filter, FieldCondition, MatchValue

        # Build filter conditions
        must_conditions = []
        if session_id:
            must_conditions.append(
                FieldCondition(key="session_id", match=MatchValue(value=session_id))
            )
        if feature:
            must_conditions.append(
                FieldCondition(key="feature", match=MatchValue(value=feature))
            )
        if test_type:
            must_conditions.append(
                FieldCondition(key="test_type", match=MatchValue(value=test_type))
            )
        if priority:
            must_conditions.append(
                FieldCondition(key="priority", match=MatchValue(value=priority))
            )
        if test_scope:
            must_conditions.append(
                FieldCondition(key="test_scope", match=MatchValue(value=test_scope))
            )

        query_filter = Filter(must=must_conditions) if must_conditions else None

        # Scroll through all test cases
        client = rag.test_cases_rag.store.client
        collection_name = rag.test_cases_rag.store.collection_name

        all_points = []
        next_offset = None

        while True:
            result = client.scroll(
                collection_name=collection_name,
                scroll_filter=query_filter,
                limit=min(limit, 100),
                offset=next_offset,
                with_payload=True,
                with_vectors=False,
            )

            points, next_offset = result
            all_points.extend(points)

            if next_offset is None or len(all_points) >= limit + offset:
                break

        # Apply offset and limit
        paginated_points = all_points[offset:offset + limit]

        # Group by feature
        features_dict = {}
        test_cases = []

        for point in paginated_points:
            payload = point.payload or {}
            feature_name = payload.get("feature", "Unknown")

            # Support both old and new field names for backward compatibility
            test_scenario = payload.get("test_scenario", "") or payload.get("requirement_description", "")
            steps_to_execute = payload.get("steps_to_execute", "") or payload.get("test_step", "")

            test_case = {
                "id": str(point.id),
                "test_case_id": payload.get("test_case_id", ""),
                "feature": feature_name,
                "priority": payload.get("priority", "P2"),
                "category": payload.get("category", "General Features"),
                "user_type": payload.get("user_type", "Any"),
                "screen_reference": payload.get("screen_reference", ""),
                "precondition": payload.get("precondition", ""),
                "test_scenario": test_scenario,
                "steps_to_execute": steps_to_execute,
                "expected_result": payload.get("expected_result", ""),
                "dev_status": payload.get("dev_status", "Not Started"),
                "qa_status": payload.get("qa_status", "Not Started"),
                "comments": payload.get("comments", ""),
                "requirement_description": test_scenario,
                "test_step": steps_to_execute,
                "test_type": payload.get("test_type", "positive"),
                "api_component": _derive_api_component(payload),
                "session_id": payload.get("session_id", ""),
                "feature_type_detected": payload.get("feature_type_detected", ""),
                "user_states": payload.get("user_states", []),
                "screens_involved": payload.get("screens_involved", []),
                "coverage_score": payload.get("coverage_score", 0),
                "generated_at": payload.get("generated_at", ""),
            }
            test_cases.append(test_case)

            if feature_name not in features_dict:
                features_dict[feature_name] = {
                    "name": feature_name,
                    "count": 0,
                    "priorities": {"P0": 0, "P1": 0, "P2": 0, "P3": 0},
                    "test_types": {},
                }
            features_dict[feature_name]["count"] += 1
            features_dict[feature_name]["priorities"][payload.get("priority", "P2")] += 1

            tt = payload.get("test_type", "positive")
            if tt not in features_dict[feature_name]["test_types"]:
                features_dict[feature_name]["test_types"][tt] = 0
            features_dict[feature_name]["test_types"][tt] += 1

        # Sort features by count
        features = sorted(features_dict.values(), key=lambda x: x["count"], reverse=True)

        return JSONResponse(content={
            "success": True,
            "test_cases": test_cases,
            "features": features,
            "total_count": len(all_points),
            "returned_count": len(test_cases),
            "offset": offset,
            "limit": limit,
        })

    except Exception as e:
        logger.error(f"Error listing test cases: {e}")
        return JSONResponse(content={
            "success": False,
            "message": str(e),
            "test_cases": [],
            "features": [],
            "total_count": 0,
        })


@router.post("/rag/similar-cases")
async def get_similar_cases(
    query: str = Form(...),
    feature_type: Optional[str] = Form(None),
    top_k: int = Form(5),
):
    """Get similar test cases from historical data.

    Args:
        query: Search query (feature name or description).
        feature_type: Optional filter by feature type (payment, auth, etc.).
        top_k: Number of results to return (default: 5).

    Returns:
        List of similar test cases with relevance scores.
    """
    rag = get_rag()

    if rag is None or not rag.enabled:
        return JSONResponse(content={
            "success": False,
            "message": "RAG system unavailable",
            "results": [],
        })

    try:
        similar_tests = rag.get_similar_tests(
            query=query,
            feature_type=feature_type,
            top_k=top_k,
        )

        return JSONResponse(content={
            "success": True,
            "query": query,
            "feature_type": feature_type,
            "results": similar_tests,
            "count": len(similar_tests),
        })

    except Exception as e:
        logger.error(f"Error getting similar cases: {e}")
        return JSONResponse(content={
            "success": False,
            "message": str(e),
            "results": [],
        })


@router.post("/rag/analyze-gaps")
async def analyze_coverage_gaps(
    feature_name: str = Form(...),
    prd_content: str = Form(""),
    test_cases_json: str = Form(...),
):
    """Analyze coverage gaps by comparing generated tests with historical patterns.

    This endpoint is called AFTER test generation to identify potentially missing
    scenarios based on what similar features have tested historically.

    Args:
        feature_name: Name of the feature being tested.
        prd_content: Optional PRD content for better matching.
        test_cases_json: JSON string of generated test cases.

    Returns:
        Gap analysis results with missing scenarios and suggested tests.
    """
    rag = get_rag()

    if not rag or not rag.enabled:
        return JSONResponse(content={
            "success": True,
            "message": "RAG not available - gap analysis skipped",
            "missing_scenarios": [],
            "suggested_tests": [],
            "confidence": 0,
        })

    try:
        test_cases_data = json.loads(test_cases_json)

        # Convert to TestCase objects
        from framework.models import TestCase
        test_cases = []
        for tc_data in test_cases_data:
            try:
                tc = TestCase(
                    test_case_id=tc_data.get("test_case_id", ""),
                    feature=tc_data.get("feature", ""),
                    requirement_description=tc_data.get("requirement_description", ""),
                    test_step=tc_data.get("test_step", ""),
                    expected_result=tc_data.get("expected_result", ""),
                    priority=tc_data.get("priority", "P2"),
                    test_type=tc_data.get("test_type", "positive"),
                )
                test_cases.append(tc)
            except Exception as e:
                logger.warning(f"Error parsing test case: {e}")
                continue

        if not test_cases:
            return JSONResponse(content={
                "success": False,
                "message": "No valid test cases provided",
                "missing_scenarios": [],
                "suggested_tests": [],
                "confidence": 0,
            })

        # Run gap analysis
        gap_results = rag.analyze_coverage_gaps(
            generated_tests=test_cases,
            feature_name=feature_name,
            prd_content=prd_content,
        )

        return JSONResponse(content={
            "success": True,
            **gap_results,
        })

    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON for test cases: {e}")
        return JSONResponse(content={
            "success": False,
            "message": f"Invalid test cases JSON: {e}",
            "missing_scenarios": [],
            "suggested_tests": [],
            "confidence": 0,
        })

    except Exception as e:
        logger.error(f"Error analyzing gaps: {e}")
        return JSONResponse(content={
            "success": False,
            "message": str(e),
            "missing_scenarios": [],
            "suggested_tests": [],
            "confidence": 0,
        })


@router.post("/rag/index-session")
async def index_session_manual(
    session_id: str = Form(...),
    csv_path: str = Form(...),
):
    """Manually trigger RAG indexing for a specific session.

    Args:
        session_id: Unique session identifier.
        csv_path: Path to the test cases CSV file.

    Returns:
        Indexing statistics.
    """
    rag = get_rag()

    if rag is None or not rag.enabled:
        return JSONResponse(content={
            "success": False,
            "message": "RAG system unavailable",
        })

    try:
        from framework.models import TestCase, TestChecklist
        import csv

        csv_file = OUTPUT_DIR / csv_path
        if not csv_file.exists():
            raise HTTPException(status_code=404, detail=f"CSV file not found: {csv_path}")

        test_cases = []
        with open(csv_file, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                tc = TestCase(
                    test_case_id=row.get("Test Case ID", row.get("TestCaseID", "")),
                    feature=row.get("Feature", ""),
                    requirement_description=row.get("Requirement Description", row.get("RequirementDescription", "")),
                    test_step=row.get("Test Steps", row.get("TestStep", "")),
                    expected_result=row.get("Expected Result", row.get("ExpectedResult", "")),
                    priority=row.get("Priority", "P2"),
                    notes=row.get("Notes", ""),
                    test_type=row.get("Test Type", row.get("TestType", "general")),
                )
                test_cases.append(tc)

        # Create mock checklist for indexing
        checklist = TestChecklist(
            feature_name=csv_path.replace("testcases_", "").replace(".csv", ""),
            test_points=[],
            coverage_score=75.0,
            coverage_analysis=None,
        )

        # Index the session
        stats = await rag.index_session(
            test_cases=test_cases,
            checklist=checklist,
            prd_content="",
            session_id=session_id,
        )

        return JSONResponse(content={
            "success": True,
            "stats": stats,
        })

    except Exception as e:
        logger.error(f"Error indexing session: {e}")
        return JSONResponse(content={
            "success": False,
            "message": str(e),
        })


@router.get("/rag/truth-table")
async def list_truth_table_entries(
    session_id: Optional[str] = None,
    feature: Optional[str] = None,
    priority: Optional[str] = None,
    test_type: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
):
    """List truth table entries from the RAG repository.

    Args:
        session_id: Optional filter by session ID.
        feature: Optional filter by feature name.
        priority: Optional filter by priority.
        test_type: Optional filter by test type (navigation, payment_redirect, etc.).
        limit: Maximum number of results (default 100).
        offset: Pagination offset.

    Returns:
        List of truth table entries.
    """
    rag = get_rag()

    if not rag or not rag.enabled:
        return JSONResponse(content={
            "success": False,
            "message": "RAG not available",
            "entries": [],
            "total_count": 0,
        })

    try:
        from qdrant_client.models import Filter, FieldCondition, MatchValue

        # Build filter conditions
        must_conditions = []
        if session_id:
            must_conditions.append(
                FieldCondition(key="session_id", match=MatchValue(value=session_id))
            )
        if feature:
            must_conditions.append(
                FieldCondition(key="feature", match=MatchValue(value=feature))
            )
        if priority:
            must_conditions.append(
                FieldCondition(key="priority", match=MatchValue(value=priority))
            )
        if test_type:
            must_conditions.append(
                FieldCondition(key="test_type", match=MatchValue(value=test_type))
            )

        query_filter = Filter(must=must_conditions) if must_conditions else None

        # Get truth table collection
        client = rag.truth_table_rag.store.client
        collection_name = rag.truth_table_rag.store.collection_name

        # Scroll through entries
        all_points = []
        scroll_offset = None

        while True:
            results = client.scroll(
                collection_name=collection_name,
                scroll_filter=query_filter,
                limit=100,
                offset=scroll_offset,
                with_payload=True,
            )

            points, scroll_offset = results
            all_points.extend(points)

            if scroll_offset is None or len(points) < 100:
                break

        # Paginate
        paginated_points = all_points[offset:offset + limit]

        # Format entries
        entries = []
        for point in paginated_points:
            payload = point.payload or {}
            entry = {
                "id": str(point.id),
                "entry_id": payload.get("entry_id", ""),
                "session_id": payload.get("session_id", ""),
                "feature_name": payload.get("feature_name", ""),
                "screen": payload.get("screen", ""),
                "checkpoint": payload.get("checkpoint", ""),
                "failed_redirect": payload.get("failed_redirect", ""),
                "pending_redirect": payload.get("pending_redirect", ""),
                "successful_redirect": payload.get("successful_redirect", ""),
                "auto_redirect_failed": payload.get("auto_redirect_failed", "NA"),
                "auto_redirect_pending": payload.get("auto_redirect_pending", "NA"),
                "auto_redirect_success": payload.get("auto_redirect_success", "Pass"),
                "result": payload.get("result", "Not Tested"),
                "expected": payload.get("expected", ""),
                "feature": payload.get("feature", ""),
                "priority": payload.get("priority", "P1"),
                "test_type": payload.get("test_type", "navigation"),
                "version": payload.get("version", 1),
                "generated_at": payload.get("generated_at", ""),
            }
            entries.append(entry)

        return JSONResponse(content={
            "success": True,
            "entries": entries,
            "total_count": len(all_points),
            "returned_count": len(entries),
        })

    except Exception as e:
        logger.error(f"Error fetching truth table entries: {e}")
        return JSONResponse(content={
            "success": False,
            "message": str(e),
            "entries": [],
            "total_count": 0,
        })


@router.post("/rag/clean-duplicates")
async def clean_duplicate_test_cases(
    session_id: Optional[str] = None,
    dry_run: bool = True,
):
    """Remove duplicate test cases from RAG database.

    Duplicates are identified by:
    1. Same test_case_id + same test_scenario (true duplicates)
    2. Same test_case_id but different content (keeps the most recent)

    Args:
        session_id: Optional filter to clean only specific session.
        dry_run: If True, only report duplicates without deleting (default: True).

    Returns:
        Report of duplicates found/removed.
    """
    rag = get_rag()

    if not rag or not rag.enabled:
        return JSONResponse(content={
            "success": False,
            "message": "RAG not available",
        })

    try:
        from collections import defaultdict

        # Get all test cases
        client = rag.test_cases_rag.store.client
        collection_name = rag.test_cases_rag.store.collection_name

        # Build filter if session_id provided
        query_filter = None
        if session_id:
            from qdrant_client.models import Filter, FieldCondition, MatchValue
            query_filter = Filter(must=[
                FieldCondition(key="session_id", match=MatchValue(value=session_id))
            ])

        all_points = client.scroll(
            collection_name=collection_name,
            scroll_filter=query_filter,
            limit=10000,
            with_payload=True,
            with_vectors=False,
        )[0]

        # Group by test_case_id
        by_id = defaultdict(list)
        for point in all_points:
            payload = point.payload or {}
            tc_id = payload.get("test_case_id", "")
            by_id[tc_id].append({
                "point_id": point.id,
                "test_case_id": tc_id,
                "test_scenario": payload.get("test_scenario", payload.get("requirement_description", "")),
                "generated_at": payload.get("generated_at", ""),
                "session_id": payload.get("session_id", ""),
            })

        # Find duplicates
        duplicates_to_remove = []
        duplicate_report = []

        for tc_id, cases in by_id.items():
            if len(cases) > 1:
                # Sort by generated_at (keep most recent)
                cases_sorted = sorted(cases, key=lambda x: x.get("generated_at", ""), reverse=True)

                # Group by scenario to find true duplicates vs ID collisions
                scenario_groups = defaultdict(list)
                for case in cases_sorted:
                    # Use full scenario text to avoid false positive duplicates
                    scenario_key = case["test_scenario"] if case["test_scenario"] else ""
                    scenario_groups[scenario_key].append(case)

                for scenario, group in scenario_groups.items():
                    if len(group) > 1:
                        # True duplicates - keep only the first (most recent)
                        keep = group[0]
                        remove = group[1:]
                        for r in remove:
                            duplicates_to_remove.append(r["point_id"])
                            duplicate_report.append({
                                "type": "true_duplicate",
                                "test_case_id": tc_id,
                                "scenario_preview": scenario[:60] + "..." if len(scenario) > 60 else scenario,
                                "keeping": keep["point_id"],
                                "removing": r["point_id"],
                            })

                # For ID collisions (same ID, different scenarios), regenerate IDs later
                if len(scenario_groups) > 1:
                    for scenario, group in list(scenario_groups.items())[1:]:
                        for case in group:
                            duplicate_report.append({
                                "type": "id_collision",
                                "test_case_id": tc_id,
                                "scenario_preview": scenario[:60] + "..." if len(scenario) > 60 else scenario,
                                "action": "needs_id_regeneration",
                                "point_id": case["point_id"],
                            })

        # Delete duplicates if not dry run
        deleted_count = 0
        if not dry_run and duplicates_to_remove:
            client.delete(
                collection_name=collection_name,
                points_selector=duplicates_to_remove,
            )
            deleted_count = len(duplicates_to_remove)
            logger.info(f"Deleted {deleted_count} duplicate test cases")

        return JSONResponse(content={
            "success": True,
            "dry_run": dry_run,
            "total_test_cases": len(all_points),
            "unique_ids": len(by_id),
            "duplicates_found": len(duplicates_to_remove),
            "id_collisions_found": sum(1 for r in duplicate_report if r.get("type") == "id_collision"),
            "deleted_count": deleted_count,
            "report": duplicate_report[:50],  # Limit report size
            "message": f"{'Would delete' if dry_run else 'Deleted'} {len(duplicates_to_remove)} true duplicates. {sum(1 for r in duplicate_report if r.get('type') == 'id_collision')} ID collisions need manual review.",
        })

    except Exception as e:
        logger.error(f"Error cleaning duplicates: {e}", exc_info=True)
        return JSONResponse(content={
            "success": False,
            "message": str(e),
        })
