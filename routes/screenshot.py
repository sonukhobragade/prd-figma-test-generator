"""Screenshot Analysis routes - streaming analysis."""

import asyncio
import json
import logging
import os
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, File, Form, UploadFile
from sse_starlette.sse import EventSourceResponse

from framework.llm_analyzer import LLMAnalyzer
from framework.messages import StreamMessages
from framework.prd_uploader import PRDUploader
from framework.test_expander import TestCaseExpander
from routes.dependencies import (
    OUTPUT_DIR,
    PRD_STORAGE_DIR,
    get_timestamp,
    index_session_background,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["Screenshot Analysis"])

# API Keys from environment
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")


@router.post("/analyze-screenshot-stream")
async def analyze_screenshot_stream(
    screenshot: UploadFile = File(...),
    feature_name: Optional[str] = Form(None),
    apply_methods: Optional[str] = Form(None),
    prd_content: Optional[str] = Form(None),
    prd_file: Optional[UploadFile] = File(None),
    llm_provider: Optional[str] = Form("openai"),
    llm_api_key: Optional[str] = Form(None),
    # VERSION TRACKING PARAMS
    version: int = Form(1),
    update_existing: bool = Form(False),
):
    """Stream screenshot analysis and test case generation with AG-UI protocol.

    Analyzes UI screenshots using vision capabilities to generate test cases.
    Supports combining with PRD content for comprehensive test coverage.

    Args:
        screenshot: Screenshot image file (PNG, JPG, JPEG).
        feature_name: Optional feature name.
        apply_methods: Comma-separated test design methods.
        prd_content: Optional PRD text content to combine with screenshot.
        prd_file: Optional PRD file upload to combine with screenshot.
        llm_provider: LLM provider ("anthropic" or "openai").
        llm_api_key: API key (optional, uses env var if not provided).
        version: Version number (default 1).
        update_existing: Whether to add tests to existing version.

    Returns:
        Server-Sent Events stream with real-time updates.
    """

    async def event_generator():
        prd_text_parts = []

        try:
            # Save uploaded screenshot
            yield {
                "event": "status",
                "data": json.dumps(
                    {
                        "type": "validation",
                        "message": "Validating screenshot file...",
                        "progress": 10,
                    }
                ),
            }

            screenshot_path = PRD_STORAGE_DIR / screenshot.filename
            with open(screenshot_path, "wb") as f:
                content = await screenshot.read()
                f.write(content)

            # Save PRD file if provided
            prd_doc_content = prd_content or ""
            if prd_file:
                prd_file_path = PRD_STORAGE_DIR / prd_file.filename
                with open(prd_file_path, "wb") as f:
                    prd_content_data = await prd_file.read()
                    f.write(prd_content_data)

                uploader = PRDUploader()
                prd_doc = uploader.upload(prd_file_path)
                prd_doc_content = prd_doc.content or ""
                prd_text_parts.append(prd_doc_content)

            if prd_content:
                prd_text_parts.append(prd_content)

            # Analyzing screenshot
            yield {
                "event": "status",
                "data": json.dumps(
                    {
                        "type": "analyzing",
                        "message": "[IMAGE] Analyzing screenshot with Claude Vision...",
                        "progress": 30,
                    }
                ),
            }

            # Parse methods
            methods = []
            if apply_methods:
                methods = [m.strip() for m in apply_methods.split(",")]

            # Determine which API key to use based on selected provider
            provider = llm_provider or "openai"
            api_key = llm_api_key
            if not api_key:
                api_key = ANTHROPIC_API_KEY if provider == "anthropic" else OPENAI_API_KEY

            if not api_key:
                yield {
                    "event": "error",
                    "data": json.dumps({
                        "message": f"No API key available for {provider}. Please set {provider.upper()}_API_KEY in .env",
                        "type": "missing_api_key"
                    }),
                }
                return

            # Analyze screenshot with LLM
            analyzer = LLMAnalyzer(api_key=api_key, provider=provider)
            checklist = analyzer.analyze_screenshot(
                screenshot_path=screenshot_path,
                prd_content=prd_doc_content,
                feature_name=feature_name,
                apply_methods=methods,
            )

            # Confirm analysis complete
            yield {
                "event": "status",
                "data": json.dumps(
                    {
                        "type": "analysis_complete",
                        "message": StreamMessages.DESIGN_RECEIVED,
                        "progress": 40,
                    }
                ),
            }

            # Save checklist
            timestamp = get_timestamp()
            checklist_path = OUTPUT_DIR / f"checklist_screenshot_{timestamp}.md"
            markdown = analyzer.generate_checklist_markdown(checklist)
            checklist_path.write_text(markdown)

            # Stream checklist items
            if checklist.test_points:
                for idx, tp in enumerate(checklist.test_points):
                    yield {
                        "event": "checklist_item",
                        "data": json.dumps(
                            {
                                "id": f"TP{idx+1:03d}",
                                "description": tp.description,
                                "feature": tp.feature,
                                "priority": tp.priority,
                                "test_type": tp.test_type,
                                "index": idx,
                                "total": len(checklist.test_points),
                                "progress": 40 + (idx / len(checklist.test_points) * 20),
                            }
                        ),
                    }
                    await asyncio.sleep(0.05)

            # Expanding test cases
            yield {
                "event": "status",
                "data": json.dumps(
                    {
                        "type": "expanding",
                        "message": "[CLIPBOARD] Expanding test points into detailed test cases...",
                        "progress": 60,
                    }
                ),
            }

            # Expand to test cases
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

            # Background RAG indexing with VERSION TRACKING
            # Session ID format: FeatureName_V{version}
            feature_name_clean = checklist.feature_name.replace(" ", "_")
            session_id = f"{feature_name_clean}_V{version}"

            # Determine documents included
            documents_included = ["screenshot"]
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
                source_document="screenshot",
                test_scope="frontend",
            ))

            # Completion event
            yield {
                "event": "complete",
                "data": json.dumps(
                    {
                        "feature_name": checklist.feature_name,
                        "test_points_count": len(checklist.test_points),
                        "test_cases_count": len(test_cases),
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
                ),
            }

        except Exception as e:
            logger.error(f"Error in analyze_screenshot_stream: {str(e)}", exc_info=True)
            yield {
                "event": "error",
                "data": json.dumps({"message": str(e), "type": "processing_error"}),
            }

    return EventSourceResponse(event_generator())
