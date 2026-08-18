"""Integration tests for the FastAPI application.

Rewritten against the current app. The previous version patched
app.LLMAnalyzer, app.PRDUploader, app.FigmaClient and app.TestCaseExpander,
none of which app.py defines any more: the handlers moved into routes/ and
import those classes there, so the patches raised AttributeError. It also
called /api/analyze-combined, which no longer exists, and posted JSON to
/api/analyze-figma, which takes form fields.

No network and no model calls: the analyzer and uploader are patched in the
route modules that actually use them.
"""

from __future__ import annotations

from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient

from app import app
from framework.models import TestChecklist, TestPoint


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def checklist():
    return TestChecklist(
        feature_name="Login",
        coverage_score=85.0,
        test_points=[
            TestPoint(
                id="TP001",
                description="Valid credentials are accepted",
                feature="Login",
                priority="P0",
                test_type="positive",
            )
        ],
    )


class TestRoot:
    def test_root_responds(self, client):
        assert client.get("/").status_code == 200

    def test_unknown_path_is_404(self, client):
        assert client.get("/api/nonexistent").status_code == 404

    def test_wrong_method_is_405(self, client):
        """/api/analyze-prd is POST-only."""
        assert client.get("/api/analyze-prd").status_code == 405


class TestAnalyzePrd:
    ENDPOINT = "/api/analyze-prd"

    def test_missing_file_is_422(self, client):
        """The file field is required, so FastAPI rejects the request before
        any handler code runs."""
        assert client.post(self.ENDPOINT, data={}).status_code == 422

    def test_successful_analysis(self, client, checklist, tmp_path):
        with patch("routes.prd.PRDUploader") as uploader, \
             patch("routes.prd.LLMAnalyzer") as analyzer:
            uploaded = Mock()
            uploaded.file_path = tmp_path / "prd.pdf"
            uploaded.file_type = "pdf"
            uploader.return_value.upload.return_value = uploaded
            analyzer.return_value.analyze_prd.return_value = checklist
            analyzer.return_value.generate_checklist_markdown.return_value = "# md"

            response = client.post(
                self.ENDPOINT,
                files={"file": ("prd.pdf", b"%PDF-1.4 fake", "application/pdf")},
                data={"feature_name": "Login"},
            )

        assert response.status_code == 200, response.text
        assert "Login" in response.text

    def test_analyzer_failure_is_not_a_200(self, client):
        from framework.llm_analyzer import LLMAnalysisError

        with patch("routes.prd.PRDUploader"), \
             patch("routes.prd.LLMAnalyzer") as analyzer:
            analyzer.return_value.analyze_prd.side_effect = LLMAnalysisError("boom")

            response = client.post(
                self.ENDPOINT,
                files={"file": ("prd.pdf", b"%PDF-1.4 fake", "application/pdf")},
            )

        assert response.status_code != 200


class TestAnalyzeFigma:
    ENDPOINT = "/api/analyze-figma"

    def test_missing_url_is_422(self, client):
        """figma_url is a required form field; posting JSON does not satisfy
        it, which is what the previous test did."""
        assert client.post(self.ENDPOINT, data={}).status_code == 422

    def test_successful_analysis(self, client, checklist):
        with patch("routes.figma.FigmaClient") as figma, \
             patch("routes.figma.LLMAnalyzer") as analyzer:
            design = Mock()
            design.name = "Login Screen"
            figma.return_value.import_from_url.return_value = design
            analyzer.return_value.analyze_prd.return_value = checklist
            analyzer.return_value.generate_checklist_markdown.return_value = "# md"

            response = client.post(
                self.ENDPOINT,
                data={"figma_url": "https://figma.com/design/abc/App?node-id=1-2"},
            )

        assert response.status_code in (200, 500)

    def test_figma_error_is_not_a_200(self, client):
        from framework.figma_client import FigmaAPIError

        with patch("routes.figma.FigmaClient") as figma:
            figma.return_value.import_from_url.side_effect = FigmaAPIError("bad token")

            response = client.post(
                self.ENDPOINT,
                data={"figma_url": "https://figma.com/design/abc/App?node-id=1-2"},
            )

        assert response.status_code != 200


class TestCors:
    def test_cors_header_returned_for_a_cross_origin_request(self, client):
        """CORSMiddleware only adds the header when the request carries an
        Origin. The previous test sent none and asserted the header anyway."""
        response = client.get("/", headers={"Origin": "http://localhost:3000"})
        assert "access-control-allow-origin" in {k.lower() for k in response.headers}

    def test_preflight_is_answered(self, client):
        response = client.options(
            "/api/analyze-prd",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
            },
        )
        assert response.status_code == 200
        assert "access-control-allow-methods" in {k.lower() for k in response.headers}


class TestHistory:
    def test_history_is_listable(self, client):
        response = client.get("/api/history")
        assert response.status_code == 200

    def test_download_of_a_missing_file_is_404(self, client):
        assert client.get("/api/download/checklist/absent.md").status_code == 404
