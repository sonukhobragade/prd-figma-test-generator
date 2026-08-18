"""PRD Analysis routes - streaming and non-streaming."""

import asyncio
import json
import logging
import os
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from framework.llm_analyzer import LLMAnalyzer
from framework.messages import StreamMessages
from framework.prd_uploader import PRDUploader
from framework.test_expander import TestCaseExpander
from routes.dependencies import (
    OUTPUT_DIR,
    PRD_STORAGE_DIR,
    AnalysisResponse,
    get_timestamp,
    index_session_background,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["PRD Analysis"])

# API Keys from environment
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")


class TestCaseResponse(BaseModel):
    """Response model for individual test case."""

    id: str
    description: str
    feature: str
    priority: str
    test_type: str


@router.post("/analyze-prd", response_model=AnalysisResponse)
async def analyze_prd(
    file: UploadFile = File(...),
    feature_name: Optional[str] = Form(None),
    apply_methods: Optional[str] = Form(None),
):
    """Analyze uploaded PRD and generate test cases (non-streaming).

    Args:
        file: Uploaded PRD file (PDF, PNG, JPG, JPEG).
        feature_name: Optional feature name.
        apply_methods: Comma-separated test design methods.

    Returns:
        Analysis results with test points and file paths.
    """
    try:
        # Save uploaded file
        file_path = PRD_STORAGE_DIR / file.filename
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)

        # Validate and process
        uploader = PRDUploader()
        if not uploader.validate_file(file_path):
            raise HTTPException(status_code=400, detail="Invalid file format or size")

        prd_doc = uploader.upload(file_path)

        # Parse methods
        methods = []
        if apply_methods:
            methods = [m.strip() for m in apply_methods.split(",")]

        # Analyze with LLM
        api_key = ANTHROPIC_API_KEY or OPENAI_API_KEY
        provider = "anthropic" if ANTHROPIC_API_KEY else "openai"
        analyzer = LLMAnalyzer(api_key=api_key, provider=provider)

        checklist = analyzer.analyze_prd(
            content=prd_doc.content or "",
            images=prd_doc.images,
            feature_name=feature_name,
            apply_methods=methods,
        )

        # Save checklist
        timestamp = get_timestamp()
        checklist_path = OUTPUT_DIR / f"checklist_{timestamp}.md"
        markdown = analyzer.generate_checklist_markdown(checklist)
        checklist_path.write_text(markdown)

        # Expand to test cases
        expander = TestCaseExpander()
        test_cases = expander.expand_checklist(checklist)
        # Format: Frontend_FeatureName_Epoch.csv
        import time
        import re
        epoch = int(time.time() * 1000)
        feature_name_safe = re.sub(r'[^a-zA-Z0-9_]', '', feature_name.replace(" ", "_"))
        testcases_path = OUTPUT_DIR / f"Frontend_{feature_name_safe}_{epoch}.csv"
        expander.export_to_csv(test_cases, testcases_path)

        # Build response
        test_points = [
            {
                "id": tp.id,
                "description": tp.description,
                "feature": tp.feature,
                "priority": tp.priority,
                "test_type": tp.test_type,
            }
            for tp in checklist.test_points
        ]

        return AnalysisResponse(
            feature_name=checklist.feature_name,
            test_points=test_points,
            coverage_score=checklist.coverage_score,
            generated_at=datetime.now().isoformat(),
            checklist_path=f"/output/{checklist_path.name}",
            testcases_path=f"/output/{testcases_path.name}",
        )

    except Exception as e:
        logger.error(f"Error in analyze_prd: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze-prd-stream")
async def analyze_prd_stream(
    file: UploadFile = File(...),
    feature_name: Optional[str] = Form(None),
    apply_methods: Optional[str] = Form(None),
    frontend_doc_file: Optional[UploadFile] = File(None),
    frontend_doc_content: Optional[str] = Form(None),
    llm_provider: Optional[str] = Form("openai"),
    llm_api_key: Optional[str] = Form(None),
    # VERSION TRACKING PARAMS
    version: int = Form(1),
    update_existing: bool = Form(False),
):
    """Stream PRD analysis and test case generation with AG-UI protocol.

    Args:
        file: Uploaded PRD file (PDF, PNG, JPG, JPEG).
        feature_name: Optional feature name.
        apply_methods: Comma-separated test design methods.
        frontend_doc_file: Optional Frontend LLD document (PDF) with screen flows, components.
        frontend_doc_content: Optional Frontend LLD content (text) - used if frontend_doc_file not provided.
        llm_provider: LLM provider ("anthropic" or "openai").
        llm_api_key: API key (optional, uses env var if not provided).
        version: Version number (default 1).
        update_existing: Whether to add tests to existing version.

    Returns:
        Server-Sent Events stream with real-time updates.
    """

    async def event_generator():
        try:
            # Save uploaded file
            yield {
                "event": "status",
                "data": json.dumps(
                    {
                        "type": "file_upload",
                        "message": "Uploading PRD file...",
                        "progress": 10,
                    }
                ),
            }

            file_path = PRD_STORAGE_DIR / file.filename
            with open(file_path, "wb") as f:
                content = await file.read()
                f.write(content)

            # Validate and process
            yield {
                "event": "status",
                "data": json.dumps(
                    {
                        "type": "validating",
                        "message": "Validating PRD document...",
                        "progress": 15,
                    }
                ),
            }

            uploader = PRDUploader()
            if not uploader.validate_file(file_path):
                yield {
                    "event": "error",
                    "data": json.dumps({"message": "Invalid file format or size"}),
                }
                return

            prd_doc = uploader.upload(file_path)

            # Process Frontend LLD document if provided
            frontend_doc = None
            if frontend_doc_file:
                yield {
                    "event": "status",
                    "data": json.dumps(
                        {
                            "type": "processing_frontend_lld",
                            "message": "Processing Frontend LLD document...",
                            "progress": 18,
                        }
                    ),
                }
                # Save and extract text from frontend doc PDF
                frontend_doc_path = PRD_STORAGE_DIR / f"frontend_lld_{frontend_doc_file.filename}"
                with open(frontend_doc_path, "wb") as f:
                    frontend_content = await frontend_doc_file.read()
                    f.write(frontend_content)

                # Extract text from PDF using PRDUploader
                frontend_uploader = PRDUploader()
                frontend_prd = frontend_uploader.upload(frontend_doc_path)
                if hasattr(frontend_prd, "content") and frontend_prd.content:
                    frontend_doc = frontend_prd.content
                elif hasattr(frontend_prd, "text_content") and frontend_prd.text_content:
                    frontend_doc = frontend_prd.text_content
                elif hasattr(frontend_prd, "extracted_text") and frontend_prd.extracted_text:
                    frontend_doc = frontend_prd.extracted_text
            elif frontend_doc_content:
                frontend_doc = frontend_doc_content
                yield {
                    "event": "status",
                    "data": json.dumps(
                        {
                            "type": "processing_frontend_lld",
                            "message": "Processing Frontend LLD content...",
                            "progress": 18,
                        }
                    ),
                }

            # Parse methods
            methods = []
            if apply_methods:
                methods = [m.strip() for m in apply_methods.split(",")]

            # Initialize LLM
            yield {
                "event": "status",
                "data": json.dumps(
                    {
                        "type": "initializing_llm",
                        "message": f"Initializing {llm_provider.upper()} analyzer...",
                        "progress": 20,
                    }
                ),
            }

            # Determine API key
            api_key = llm_api_key
            if not api_key:
                api_key = ANTHROPIC_API_KEY if llm_provider == "anthropic" else OPENAI_API_KEY

            analyzer = LLMAnalyzer(api_key=api_key, provider=llm_provider)

            # Get PRD content for analysis
            prd_content = None
            if hasattr(prd_doc, "text_content") and prd_doc.text_content:
                prd_content = prd_doc.text_content
            elif hasattr(prd_doc, "extracted_text") and prd_doc.extracted_text:
                prd_content = prd_doc.extracted_text
            elif hasattr(prd_doc, "content") and prd_doc.content:
                prd_content = prd_doc.content
            else:
                prd_content = str(prd_doc)

            # Analyze PRD
            has_frontend_lld = frontend_doc is not None
            yield {
                "event": "status",
                "data": json.dumps(
                    {
                        "type": "analyzing",
                        "message": f"Generating {'comprehensive ' if has_frontend_lld else ''}frontend test cases...",
                        "progress": 30,
                        "has_frontend_lld": has_frontend_lld,
                    }
                ),
            }

            checklist = analyzer.analyze_prd(
                content=prd_content or "",
                images=prd_doc.images if hasattr(prd_doc, "images") else [],
                feature_name=feature_name or prd_doc.filename,
                apply_methods=methods,
                frontend_doc=frontend_doc,
            )

            # Analysis complete
            yield {
                "event": "status",
                "data": json.dumps(
                    {
                        "type": "analysis_complete",
                        "message": StreamMessages.ANALYSIS_COMPLETE,
                        "progress": 48,
                    }
                ),
            }

            # Emit checklist info
            yield {
                "event": "checklist_generated",
                "data": json.dumps(
                    {
                        "feature_name": checklist.feature_name,
                        "test_points_count": len(checklist.test_points),
                        "truth_table_count": len(checklist.truth_table_entries) if hasattr(checklist, "truth_table_entries") else 0,
                        "coverage_score": checklist.coverage_score,
                        "progress": 50,
                    }
                ),
            }

            # Stream each test point
            for idx, test_point in enumerate(checklist.test_points):
                yield {
                    "event": "test_point",
                    "data": json.dumps(
                        {
                            "id": test_point.id,
                            "description": test_point.description,
                            "feature": test_point.feature,
                            "priority": test_point.priority,
                            "test_type": test_point.test_type,
                            "index": idx,
                            "total": len(checklist.test_points),
                        }
                    ),
                }

            # Stream truth table entries if any
            if hasattr(checklist, "truth_table_entries") and checklist.truth_table_entries:
                yield {
                    "event": "status",
                    "data": json.dumps(
                        {
                            "type": "streaming_truth_table",
                            "message": f"Streaming {len(checklist.truth_table_entries)} truth table entries...",
                            "progress": 55,
                        }
                    ),
                }

                for idx, entry in enumerate(checklist.truth_table_entries):
                    yield {
                        "event": "truth_table_entry",
                        "data": json.dumps(
                            {
                                "id": entry.id,
                                "screen": entry.screen,
                                "checkpoint": entry.checkpoint,
                                "failed_redirect": entry.failed_redirect,
                                "pending_redirect": entry.pending_redirect,
                                "successful_redirect": entry.successful_redirect,
                                "auto_redirect_failed": entry.auto_redirect_failed,
                                "auto_redirect_pending": entry.auto_redirect_pending,
                                "auto_redirect_success": entry.auto_redirect_success,
                                "result": entry.result,
                                "expected": entry.expected,
                                "feature": entry.feature,
                                "priority": entry.priority,
                                "test_type": entry.test_type,
                                "index": idx,
                                "total": len(checklist.truth_table_entries),
                            }
                        ),
                    }

            # Save checklist
            yield {
                "event": "status",
                "data": json.dumps(
                    {
                        "type": "saving_checklist",
                        "message": "Saving checklist...",
                        "progress": 60,
                    }
                ),
            }

            timestamp = get_timestamp()
            checklist_path = OUTPUT_DIR / f"checklist_{timestamp}.md"
            markdown = analyzer.generate_checklist_markdown(checklist)
            checklist_path.write_text(markdown)

            # Expand to test cases
            yield {
                "event": "status",
                "data": json.dumps(
                    {
                        "type": "expanding_testcases",
                        "message": "Generating detailed test cases...",
                        "progress": 70,
                    }
                ),
            }

            expander = TestCaseExpander()
            test_cases = expander.expand_checklist(checklist)

            # Stream each test case
            for idx, test_case in enumerate(test_cases):
                yield {
                    "event": "test_case",
                    "data": json.dumps(
                        {
                            "id": test_case.test_case_id,
                            "feature": test_case.feature,
                            "requirement_description": test_case.requirement_description,
                            "test_step": test_case.test_step,
                            "expected_result": test_case.expected_result,
                            "priority": test_case.priority,
                            "notes": test_case.notes,
                            "index": idx,
                            "total": len(test_cases),
                            "progress": 70 + (idx / len(test_cases) * 20),
                        }
                    ),
                }

            # Save CSV - Format: Frontend_FeatureName_Epoch.csv
            import time
            import re
            epoch = int(time.time() * 1000)
            feature_name_safe = re.sub(r'[^a-zA-Z0-9_]', '', checklist.feature_name.replace(" ", "_"))
            testcases_path = OUTPUT_DIR / f"Frontend_{feature_name_safe}_{epoch}.csv"
            expander.export_to_csv(test_cases, testcases_path)

            # Export truth table CSV if entries exist
            truth_table_path = None
            if hasattr(checklist, "truth_table_entries") and checklist.truth_table_entries:
                truth_table_path = OUTPUT_DIR / f"TruthTable_{feature_name_safe}_{epoch}.csv"
                expander.export_truth_table_to_csv(checklist.truth_table_entries, truth_table_path)

            # Background RAG indexing with VERSION TRACKING
            # Session ID format: FeatureName_V{version}
            feature_name_clean = checklist.feature_name.replace(" ", "_")
            session_id = f"{feature_name_clean}_V{version}"

            # Determine documents included
            documents_included = ["prd"]
            if frontend_doc is not None:
                documents_included.append("frontend_lld")

            asyncio.create_task(index_session_background(
                test_cases=test_cases,
                checklist=checklist,
                prd_content=prd_content if prd_content else "",
                session_id=session_id,
                version=version,
                documents_included=documents_included,
                source_document="frontend_lld" if frontend_doc else "prd",
                test_scope="frontend",
            ))

            # Completion event
            completion_data = {
                "feature_name": checklist.feature_name,
                "test_points_count": len(checklist.test_points),
                "test_cases_count": len(test_cases),
                "truth_table_count": len(checklist.truth_table_entries) if hasattr(checklist, "truth_table_entries") else 0,
                "coverage_score": checklist.coverage_score,
                "checklist_path": f"/output/{checklist_path.name}",
                "testcases_path": f"/output/{testcases_path.name}",
                "generated_at": datetime.now().isoformat(),
                "progress": 100,
                "rag_session_id": session_id,
                # VERSION TRACKING
                "version": version,
                "documents_included": documents_included,
                "test_scope": "frontend",
            }
            # Add coverage analysis details (missing scenarios, recommendations, distribution)
            if checklist.coverage_analysis:
                ca = checklist.coverage_analysis
                completion_data["coverage_analysis"] = {
                    "missing_scenarios": ca.missing_scenarios or [],
                    "recommendations": ca.recommendations or [],
                    "risk_assessment": {
                        "high_risk_features": ca.risk_assessment.high_risk_features if ca.risk_assessment else [],
                        "medium_risk_features": ca.risk_assessment.medium_risk_features if ca.risk_assessment else [],
                        "low_risk_features": ca.risk_assessment.low_risk_features if ca.risk_assessment else [],
                    },
                    "test_type_distribution": {
                        "positive": ca.test_type_distribution.positive if ca.test_type_distribution else 0,
                        "negative": ca.test_type_distribution.negative if ca.test_type_distribution else 0,
                        "boundary": ca.test_type_distribution.boundary if ca.test_type_distribution else 0,
                        "edge_case": ca.test_type_distribution.edge_case if ca.test_type_distribution else 0,
                    },
                    "feature_coverage": [
                        {
                            "feature": fc.feature,
                            "coverage_percentage": fc.coverage_percentage,
                            "test_count": fc.test_count,
                            "missing_scenarios": fc.missing_scenarios,
                            "risk_level": fc.risk_level,
                        }
                        for fc in (ca.feature_coverage or [])
                    ],
                }
            if truth_table_path:
                completion_data["truth_table_path"] = f"/output/{truth_table_path.name}"

            yield {
                "event": "complete",
                "data": json.dumps(completion_data),
            }

        except Exception as e:
            logger.error(f"Error in analyze_prd_stream: {str(e)}", exc_info=True)
            yield {
                "event": "error",
                "data": json.dumps({"message": str(e), "type": "processing_error"}),
            }

    return EventSourceResponse(event_generator())
