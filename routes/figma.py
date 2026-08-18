"""Figma Analysis routes - streaming and non-streaming."""

import asyncio
import json
import logging
import os
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from sse_starlette.sse import EventSourceResponse

from framework.figma_client import FigmaClient
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
router = APIRouter(prefix="/api", tags=["Figma Analysis"])

# API Keys from environment
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
FIGMA_ACCESS_TOKEN = os.getenv("FIGMA_ACCESS_TOKEN")


@router.post("/analyze-figma", response_model=AnalysisResponse)
async def analyze_figma(
    figma_url: str = Form(...),
    feature_name: Optional[str] = Form(None),
    apply_methods: Optional[str] = Form(None),
):
    """Analyze Figma design and generate test cases (non-streaming).

    Args:
        figma_url: Figma design URL.
        feature_name: Optional feature name.
        apply_methods: Comma-separated test design methods.

    Returns:
        Analysis results with test points and file paths.
    """
    try:
        # Extract Figma structure
        figma_client = FigmaClient(api_token=FIGMA_ACCESS_TOKEN)
        figma_structure = figma_client.import_from_url(figma_url)

        # Parse methods
        methods = []
        if apply_methods:
            methods = [m.strip() for m in apply_methods.split(",")]

        # Analyze with LLM
        api_key = ANTHROPIC_API_KEY or OPENAI_API_KEY
        provider = "anthropic" if ANTHROPIC_API_KEY else "openai"
        analyzer = LLMAnalyzer(api_key=api_key, provider=provider)

        checklist = analyzer.analyze_figma(
            figma_structure=figma_structure,
            feature_name=feature_name,
            apply_methods=methods,
        )

        # Save checklist
        timestamp = get_timestamp()
        checklist_path = OUTPUT_DIR / f"checklist_figma_{timestamp}.md"
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
        logger.error(f"Error in analyze_figma: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze-figma-stream")
async def analyze_figma_stream(
    figma_url: str = Form(...),
    feature_name: Optional[str] = Form(None),
    apply_methods: Optional[str] = Form(None),
    prd_content: Optional[str] = Form(None),
    prd_file: Optional[UploadFile] = File(None),
    llm_provider: Optional[str] = Form("anthropic"),
    llm_api_key: Optional[str] = Form(None),
    # VERSION TRACKING PARAMS
    version: int = Form(1),
    update_existing: bool = Form(False),
):
    """Stream Figma analysis and test case generation with AG-UI protocol.

    Supports combined Figma + PRD analysis for comprehensive test coverage.

    Args:
        figma_url: Figma design URL (required).
        feature_name: Optional feature name.
        apply_methods: Comma-separated test design methods.
        prd_content: Optional PRD text content to combine with Figma.
        prd_file: Optional PRD file to combine with Figma.
        llm_provider: LLM provider ("anthropic" or "openai").
        llm_api_key: API key (optional, uses env var if not provided).
        version: Version number (default 1).
        update_existing: Whether to add tests to existing version.

    Returns:
        Server-Sent Events stream with real-time updates.
    """

    async def event_generator():
        try:
            prd_text_parts = []

            # Extract Figma structure
            yield {
                "event": "status",
                "data": json.dumps(
                    {
                        "type": "extracting_figma",
                        "message": StreamMessages.EXTRACTING_FIGMA,
                        "progress": 10,
                    }
                ),
            }

            figma_client = FigmaClient(api_token=FIGMA_ACCESS_TOKEN)
            figma_structure = figma_client.import_from_url(figma_url)

            yield {
                "event": "status",
                "data": json.dumps(
                    {
                        "type": "figma_extracted",
                        "message": StreamMessages.FIGMA_EXTRACTED,
                        "progress": 20,
                    }
                ),
            }

            # Process PRD file if provided
            if prd_file:
                yield {
                    "event": "status",
                    "data": json.dumps(
                        {
                            "type": "processing_prd",
                            "message": "Processing PRD file...",
                            "progress": 25,
                        }
                    ),
                }

                file_path = PRD_STORAGE_DIR / prd_file.filename
                with open(file_path, "wb") as f:
                    content = await prd_file.read()
                    f.write(content)

                uploader = PRDUploader()
                if uploader.validate_file(file_path):
                    prd_doc = uploader.upload(file_path)
                    if hasattr(prd_doc, "text_content") and prd_doc.text_content:
                        prd_text_parts.append(prd_doc.text_content)
                    elif hasattr(prd_doc, "content") and prd_doc.content:
                        prd_text_parts.append(prd_doc.content)

            # Add PRD text content if provided
            if prd_content and prd_content.strip():
                prd_text_parts.append(prd_content.strip())

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
                        "progress": 30,
                    }
                ),
            }

            api_key = llm_api_key
            if not api_key:
                api_key = ANTHROPIC_API_KEY if llm_provider == "anthropic" else OPENAI_API_KEY

            analyzer = LLMAnalyzer(api_key=api_key, provider=llm_provider)

            # Analyze Figma (with optional PRD context)
            yield {
                "event": "status",
                "data": json.dumps(
                    {
                        "type": "analyzing",
                        "message": StreamMessages.ANALYZING_DESIGN,
                        "progress": 35,
                    }
                ),
            }

            combined_prd = "\n\n".join(prd_text_parts) if prd_text_parts else None

            checklist = analyzer.analyze_figma(
                figma_structure=figma_structure,
                feature_name=feature_name,
                apply_methods=methods,
                prd_content=combined_prd,
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

            # Stream test points
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

            # Stream truth table entries
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
            checklist_path = OUTPUT_DIR / f"checklist_figma_{timestamp}.md"
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

            # Stream test cases
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

            # Export truth table CSV
            truth_table_path = None
            if hasattr(checklist, "truth_table_entries") and checklist.truth_table_entries:
                truth_table_path = OUTPUT_DIR / f"TruthTable_{feature_name_safe}_{epoch}.csv"
                expander.export_truth_table_to_csv(checklist.truth_table_entries, truth_table_path)

            # Background RAG indexing with VERSION TRACKING
            # Session ID format: FeatureName_V{version}
            feature_name_clean = checklist.feature_name.replace(" ", "_")
            session_id = f"{feature_name_clean}_V{version}"

            # Determine documents included
            documents_included = ["figma"]
            if prd_text_parts:
                documents_included.append("prd")

            prd_for_rag = "\n".join(prd_text_parts) if prd_text_parts else ""
            asyncio.create_task(index_session_background(
                test_cases=test_cases,
                checklist=checklist,
                prd_content=prd_for_rag,
                session_id=session_id,
                version=version,
                documents_included=documents_included,
                source_document="figma",
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
            if truth_table_path:
                completion_data["truth_table_path"] = f"/output/{truth_table_path.name}"

            yield {
                "event": "complete",
                "data": json.dumps(completion_data),
            }

        except Exception as e:
            logger.error(f"Error in analyze_figma_stream: {str(e)}", exc_info=True)
            yield {
                "event": "error",
                "data": json.dumps({"message": str(e), "type": "processing_error"}),
            }

    return EventSourceResponse(event_generator())
