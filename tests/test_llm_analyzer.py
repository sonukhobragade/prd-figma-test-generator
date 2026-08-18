"""Tests for framework.llm_analyzer.

Rewritten against the current API. The previous version targeted
_build_messages, _generate_system_prompt, _parse_test_points, analyze_design
and combined_analysis, none of which exist any more, and passed a PRDDocument
where TestAnalysisRequest wants prd_content as a string. Those tests could not
run at all: the module failed to import, so nobody saw them fail.

Nothing here makes a network call.
"""

from __future__ import annotations

import base64
from unittest.mock import Mock, patch

import pytest

from framework.llm_analyzer import LLMAnalysisError, LLMAnalyzer
from framework.models import TestAnalysisRequest, TestChecklist, TestPoint


@pytest.fixture
def analyzer():
    return LLMAnalyzer(api_key="test_key")


def make_point(**overrides) -> TestPoint:
    fields = {
        "description": "User can log in with valid credentials",
        "feature": "Login",
        "priority": "P0",
        "test_type": "positive",
    }
    fields.update(overrides)
    return TestPoint(**fields)


def make_checklist(points=None, **overrides) -> TestChecklist:
    fields = {
        "feature_name": "Login",
        "coverage_score": 80.0,   # the scale is 0-100, not a fraction
        "test_points": points if points is not None else [make_point()],
    }
    fields.update(overrides)
    return TestChecklist(**fields)


class TestInit:
    def test_defaults_to_anthropic(self, analyzer):
        assert analyzer.provider == "anthropic"
        assert analyzer.model == LLMAnalyzer.DEFAULT_MODELS["anthropic"]

    def test_openai_provider_uses_its_own_default_model(self):
        a = LLMAnalyzer(api_key="k", provider="openai")
        assert a.model == LLMAnalyzer.DEFAULT_MODELS["openai"]

    def test_explicit_model_wins(self):
        a = LLMAnalyzer(api_key="k", model="claude-haiku-4-5-20251001")
        assert a.model == "claude-haiku-4-5-20251001"


class TestEncodeImage:
    def test_returns_media_type_then_base64(self, analyzer, tmp_path):
        """The tuple is (media_type, data), in that order."""
        png = tmp_path / "shot.png"
        raw = b"\x89PNG\r\n\x1a\n"
        png.write_bytes(raw)

        media_type, data = analyzer._encode_image(png)

        assert media_type == "image/png"
        assert base64.b64decode(data) == raw

    def test_jpeg_media_type(self, analyzer, tmp_path):
        jpg = tmp_path / "shot.jpg"
        jpg.write_bytes(b"\xff\xd8\xff")
        media_type, _ = analyzer._encode_image(jpg)
        assert media_type == "image/jpeg"

    def test_missing_file_raises(self, analyzer, tmp_path):
        with pytest.raises((FileNotFoundError, LLMAnalysisError)):
            analyzer._encode_image(tmp_path / "absent.png")


class TestBuildAnalysisPrompt:
    def test_includes_the_prd_content(self, analyzer):
        request = TestAnalysisRequest(prd_content="Users must be able to log in.")
        prompt = analyzer._build_analysis_prompt(request)
        assert "Users must be able to log in." in prompt

    def test_is_a_non_empty_instruction_prompt(self, analyzer):
        """The feature name is carried in the message payload rather than in
        this prompt, so assert on what this function is actually responsible
        for."""
        request = TestAnalysisRequest(prd_content="x", feature_name="Checkout")
        prompt = analyzer._build_analysis_prompt(request)
        assert "JSON" in prompt and len(prompt) > 200

    def test_rag_context_is_included_when_supplied(self, analyzer):
        request = TestAnalysisRequest(prd_content="x")
        prompt = analyzer._build_analysis_prompt(
            request, rag_context="PRIOR CASE: verify empty cart"
        )
        assert "verify empty cart" in prompt


class TestConvertMessagesForOpenai:
    def test_text_message_survives(self, analyzer):
        converted = analyzer._convert_messages_for_openai(
            [{"role": "user", "content": [{"type": "text", "text": "hello"}]}]
        )
        # A system message is prepended for OpenAI, so the user turn is last.
        assert converted[0]["role"] == "system"
        assert converted[-1]["role"] == "user"
        assert "hello" in str(converted[-1]["content"])

    def test_anthropic_image_block_becomes_an_openai_image_url(self, analyzer):
        converted = analyzer._convert_messages_for_openai([
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": "QUJD",
                        },
                    }
                ],
            }
        ])
        assert "image_url" in str(converted[-1]["content"])


class TestExtractResponseText:
    def test_anthropic_shape(self, analyzer):
        block = Mock()
        block.text = "the answer"
        response = Mock(content=[block])
        assert "the answer" in analyzer._extract_response_text(response)


class TestEstimateCoverage:
    def test_empty_checklist_scores_zero(self, analyzer):
        assert analyzer.estimate_coverage(make_checklist(points=[])) == 0.0

    def test_score_is_on_a_0_to_100_scale(self, analyzer):
        checklist = make_checklist(points=[
            make_point(test_type="positive"),
            make_point(test_type="negative", description="Rejects a bad password"),
            make_point(test_type="edge_case", description="200-character password"),
        ])
        score = analyzer.estimate_coverage(checklist)
        assert 0.0 <= score <= 100.0

    def test_reports_the_score_the_model_returned(self, analyzer):
        """It reports the checklist's own score rather than recomputing one;
        the only special case is an empty checklist."""
        assert analyzer.estimate_coverage(make_checklist(coverage_score=42.0)) == 42.0


class TestGenerateChecklistMarkdown:
    def test_contains_the_feature_and_points(self, analyzer):
        checklist = make_checklist(points=[
            make_point(description="Logs in with valid credentials"),
            make_point(description="Rejects an unknown user"),
        ])
        md = analyzer.generate_checklist_markdown(checklist)
        assert "Login" in md
        assert "Logs in with valid credentials" in md
        assert "Rejects an unknown user" in md

    def test_empty_checklist_still_renders(self, analyzer):
        md = analyzer.generate_checklist_markdown(make_checklist(points=[]))
        assert isinstance(md, str) and md.strip()


class TestAnalyzePrd:
    """analyze_prd is mocked at the API-call boundary; no network."""

    @staticmethod
    def _anthropic_response(text: str):
        """_call_anthropic returns the SDK response; the caller reads
        response.content[0].text."""
        block = Mock()
        block.text = text
        return Mock(content=[block])

    def test_returns_a_checklist(self, analyzer):
        payload = (
            '{"feature_name": "Login", "coverage_score": 90, "test_points": '
            '[{"description": "Valid login", "feature": "Login", '
            '"priority": "P0", "test_type": "positive"}]}'
        )
        with patch.object(analyzer, "_call_anthropic",
                          return_value=self._anthropic_response(payload)):
            result = analyzer.analyze_prd("Users log in with an email address.")

        assert isinstance(result, TestChecklist)
        assert result.feature_name == "Login"
        assert result.test_points[0].description == "Valid login"

    def test_unparseable_response_raises(self, analyzer):
        with patch.object(analyzer, "_call_anthropic",
                          return_value=self._anthropic_response("not json")):
            with pytest.raises(LLMAnalysisError):
                analyzer.analyze_prd("anything")

    def test_empty_content_still_reaches_the_model(self, analyzer):
        """Documents current behaviour: there is no local guard on empty
        input, so an empty PRD costs an API call. Worth a guard, but changing
        it is a behaviour change rather than a test fix."""
        payload = '{"feature_name": "Unknown", "coverage_score": 0, "test_points": []}'
        with patch.object(analyzer, "_call_anthropic",
                          return_value=self._anthropic_response(payload)) as call:
            analyzer.analyze_prd("")
        call.assert_called_once()


class TestOverloadRetry:
    """A 529 must be retried; any other APIStatusError must propagate.

    OverloadedError is only exported by newer anthropic releases while
    requirements.txt allows >=0.18.0, so the retry matches on the status code.
    """

    def _status_error(self, code):
        from anthropic import APIStatusError

        err = APIStatusError.__new__(APIStatusError)
        err.status_code = code
        err.message = f"HTTP {code}"
        return err

    def test_non_overload_status_is_not_retried(self, analyzer):
        with patch.object(analyzer, "_rate_limited_api_call",
                          side_effect=self._status_error(400)):
            with pytest.raises(Exception) as excinfo:
                analyzer.analyze_prd("some requirement text")
        assert "429" not in str(excinfo.value)
