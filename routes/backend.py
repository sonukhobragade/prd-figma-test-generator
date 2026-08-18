"""Backend Test Generation routes - API, Database, Security, Performance tests."""

import asyncio
import json
import logging
import os
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from sse_starlette.sse import EventSourceResponse

from framework.llm_analyzer import LLMAnalyzer
from framework.prd_uploader import PRDUploader
from framework.test_expander import TestCaseExpander
from routes.dependencies import OUTPUT_DIR, PRD_STORAGE_DIR, index_session_background

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["Backend Test Generation"])

# API Keys from environment
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")


@router.post("/analyze-prd-backend-stream")
async def analyze_prd_backend_stream(
    file: UploadFile = File(...),
    feature_name: Optional[str] = Form(None),
    backend_doc_file: Optional[UploadFile] = File(None),
    backend_doc_content: Optional[str] = Form(None),
    llm_provider: Optional[str] = Form("anthropic"),
    llm_api_key: Optional[str] = Form(None),
    # VERSION TRACKING PARAMS
    version: int = Form(1),
    update_existing: bool = Form(False),
):
    """Stream BACKEND test case generation (API, Database, Security, Performance).

    Generates backend-specific test cases from PRD, focusing on:
    - API endpoint testing (CRUD, validation, error codes)
    - Database testing (records, constraints, integrity)
    - Security testing (auth, injection, access control)
    - Performance testing (response times, load)

    Args:
        file: Uploaded PRD file (PDF, PNG, JPG, JPEG).
        feature_name: Optional feature name.
        backend_doc_file: Optional Backend LLD document (PDF) with API specs, DB schema.
        backend_doc_content: Optional Backend LLD content (text) - used if backend_doc_file not provided.
        llm_provider: LLM provider ("anthropic" or "openai").
        llm_api_key: API key (optional, uses env var if not provided).
        version: Version number (default 1).
        update_existing: Whether to add tests to existing version.

    Returns:
        Server-Sent Events stream with backend test cases.
    """

    async def event_generator():
        try:
            # Save uploaded file
            yield {
                "event": "status",
                "data": json.dumps(
                    {
                        "type": "file_upload",
                        "message": "Uploading PRD file for backend analysis...",
                        "progress": 10,
                    }
                ),
            }

            file_path = PRD_STORAGE_DIR / file.filename
            with open(file_path, "wb") as f:
                content = await file.read()
                f.write(content)

            # Process Backend LLD document if provided
            backend_doc = None
            if backend_doc_file:
                yield {
                    "event": "status",
                    "data": json.dumps(
                        {
                            "type": "processing_backend_lld",
                            "message": "Processing Backend LLD document...",
                            "progress": 15,
                        }
                    ),
                }
                # Save and extract text from backend doc PDF
                backend_doc_path = PRD_STORAGE_DIR / f"backend_lld_{backend_doc_file.filename}"
                with open(backend_doc_path, "wb") as f:
                    backend_content = await backend_doc_file.read()
                    f.write(backend_content)

                # Extract text from PDF using PRDUploader
                backend_uploader = PRDUploader()
                backend_prd = backend_uploader.upload(backend_doc_path)
                if hasattr(backend_prd, "content") and backend_prd.content:
                    backend_doc = backend_prd.content
                elif hasattr(backend_prd, "text_content") and backend_prd.text_content:
                    backend_doc = backend_prd.text_content
                elif hasattr(backend_prd, "extracted_text") and backend_prd.extracted_text:
                    backend_doc = backend_prd.extracted_text
            elif backend_doc_content:
                backend_doc = backend_doc_content
                yield {
                    "event": "status",
                    "data": json.dumps(
                        {
                            "type": "processing_backend_lld",
                            "message": "Processing Backend LLD content...",
                            "progress": 15,
                        }
                    ),
                }

            # Validate and process PRD
            yield {
                "event": "status",
                "data": json.dumps(
                    {
                        "type": "processing_prd",
                        "message": "Processing PRD document...",
                        "progress": 20,
                    }
                ),
            }

            uploader = PRDUploader()
            if not uploader.validate_file(file_path):
                raise HTTPException(status_code=400, detail="Invalid file format or size")

            prd_doc = uploader.upload(file_path)

            # Initialize LLM analyzer
            yield {
                "event": "status",
                "data": json.dumps(
                    {
                        "type": "initializing_llm",
                        "message": f"Initializing {llm_provider.upper()} analyzer for backend tests...",
                        "progress": 30,
                    }
                ),
            }

            # Determine API key
            api_key = llm_api_key
            if not api_key:
                api_key = ANTHROPIC_API_KEY if llm_provider == "anthropic" else OPENAI_API_KEY

            analyzer = LLMAnalyzer(api_key=api_key, provider=llm_provider)

            # Get PRD content
            prd_content = None
            if hasattr(prd_doc, "text_content") and prd_doc.text_content:
                prd_content = prd_doc.text_content
            elif hasattr(prd_doc, "extracted_text") and prd_doc.extracted_text:
                prd_content = prd_doc.extracted_text
            elif hasattr(prd_doc, "content") and prd_doc.content:
                prd_content = prd_doc.content
            else:
                prd_content = str(prd_doc)

            # Analyze PRD for BACKEND tests
            has_backend_lld = backend_doc is not None
            yield {
                "event": "status",
                "data": json.dumps(
                    {
                        "type": "analyzing_backend",
                        "message": f"Generating {'comprehensive ' if has_backend_lld else ''}backend test cases (API, Database, Security)...",
                        "progress": 40,
                        "has_backend_lld": has_backend_lld,
                    }
                ),
            }

            backend_checklist = analyzer.analyze_prd_backend(
                content=prd_content,
                feature_name=feature_name or prd_doc.filename,
                backend_doc=backend_doc,
            )

            # Analysis complete
            yield {
                "event": "status",
                "data": json.dumps(
                    {
                        "type": "analysis_complete",
                        "message": "Backend analysis complete!",
                        "progress": 50,
                    }
                ),
            }

            # Emit backend checklist summary
            yield {
                "event": "backend_checklist_generated",
                "data": json.dumps(
                    {
                        "feature_name": backend_checklist.feature_name,
                        "test_points_count": len(backend_checklist.test_points),
                        "api_test_count": backend_checklist.api_test_count,
                        "database_test_count": backend_checklist.database_test_count,
                        "security_test_count": backend_checklist.security_test_count,
                        "performance_test_count": backend_checklist.performance_test_count,
                        "coverage_score": backend_checklist.coverage_score,
                        "progress": 55,
                    }
                ),
            }

            # Stream each backend test point
            for idx, test_point in enumerate(backend_checklist.test_points):
                yield {
                    "event": "backend_test_point",
                    "data": json.dumps(
                        {
                            "id": test_point.id,
                            "category": test_point.category,
                            "subcategory": test_point.subcategory,
                            "api_component": test_point.api_component,
                            "test_scenario": test_point.test_scenario,
                            "precondition": test_point.precondition,
                            "verification_method": test_point.verification_method,
                            "expected_result": test_point.expected_result,
                            "priority": test_point.priority,
                            "test_type": test_point.test_type,
                            "index": idx,
                            "total": len(backend_checklist.test_points),
                        }
                    ),
                }

            # Expand to detailed backend test cases
            yield {
                "event": "status",
                "data": json.dumps(
                    {
                        "type": "expanding_backend_testcases",
                        "message": "Generating detailed backend test cases...",
                        "progress": 70,
                    }
                ),
            }

            expander = TestCaseExpander()
            backend_test_cases = expander.expand_backend_checklist(backend_checklist)

            # Stream each backend test case
            for idx, test_case in enumerate(backend_test_cases):
                yield {
                    "event": "backend_test_case",
                    "data": json.dumps(
                        {
                            "test_case_id": test_case.test_case_id,
                            "category": test_case.category,
                            "subcategory": test_case.subcategory,
                            "api_component": test_case.api_component,
                            "test_scenario": test_case.test_scenario,
                            "precondition": test_case.precondition,
                            "verification_method": test_case.verification_method,
                            "expected_result": test_case.expected_result,
                            "priority": test_case.priority,
                            "test_type": test_case.test_type,
                            "index": idx,
                            "total": len(backend_test_cases),
                            "progress": 70 + (idx / len(backend_test_cases) * 20),
                        }
                    ),
                }

            # Save backend CSV
            # Format: Backend_FeatureName_Epoch.csv
            import time
            epoch = int(time.time() * 1000)
            feature_name_safe = backend_checklist.feature_name.replace(" ", "_").replace("/", "_")
            # Remove special chars but keep alphanumeric and underscores
            import re
            feature_name_safe = re.sub(r'[^a-zA-Z0-9_]', '', feature_name_safe)
            backend_csv_path = OUTPUT_DIR / f"Backend_{feature_name_safe}_{epoch}.csv"
            expander.export_backend_to_csv(backend_test_cases, backend_csv_path)

            # Generate summary report
            summary = expander.generate_backend_summary_report(backend_test_cases)

            # Background RAG indexing with VERSION TRACKING
            # Session ID format: FeatureName_V{version}
            feature_name_clean = backend_checklist.feature_name.replace(" ", "_")
            session_id = f"{feature_name_clean}_V{version}"

            # Determine documents included
            documents_included = ["prd"]
            if backend_doc is not None:
                documents_included.append("backend_lld")

            asyncio.create_task(index_session_background(
                test_cases=backend_test_cases,
                checklist=backend_checklist,
                prd_content=prd_content if prd_content else "",
                session_id=session_id,
                version=version,
                documents_included=documents_included,
                source_document="backend_lld" if backend_doc else "prd",
                test_scope="backend",
            ))

            # Completion event
            yield {
                "event": "complete",
                "data": json.dumps(
                    {
                        "feature_name": backend_checklist.feature_name,
                        "test_points_count": len(backend_checklist.test_points),
                        "test_cases_count": len(backend_test_cases),
                        "api_test_count": summary["by_test_type"].get("API", 0),
                        "database_test_count": summary["by_test_type"].get("Database", 0),
                        "security_test_count": summary["by_test_type"].get("Security", 0),
                        "performance_test_count": summary["by_test_type"].get("Performance", 0),
                        "coverage_score": backend_checklist.coverage_score,
                        "backend_csv_path": f"/output/{backend_csv_path.name}",
                        "generated_at": datetime.now().isoformat(),
                        "progress": 100,
                        "test_scope": "backend",
                        # VERSION TRACKING
                        "version": version,
                        "documents_included": documents_included,
                        "rag_session_id": session_id,
                    }
                ),
            }

        except Exception as e:
            logger.error(f"Error in analyze_prd_backend_stream: {str(e)}", exc_info=True)
            yield {
                "event": "error",
                "data": json.dumps({"message": str(e), "type": "processing_error"}),
            }

    return EventSourceResponse(event_generator())
