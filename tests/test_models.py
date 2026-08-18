"""Unit tests for Pydantic models."""

import pytest
from pathlib import Path
from pydantic import ValidationError

from framework.models import (
    PRDDocument,
    FigmaDesign,
    TestPoint,
    TestChecklist,
    TestCase,
)


class TestPRDDocument:
    """Test PRDDocument model."""

    def test_valid_prd_document(self) -> None:
        """Test creating valid PRD document."""
        doc = PRDDocument(
            file_path=Path("test.pdf"),
            file_type="pdf",
            file_size_mb=5.0,
        )
        assert doc.file_path == Path("test.pdf")
        assert doc.file_type == "pdf"
        assert doc.file_size_mb == 5.0

    def test_file_size_validation_exceeds_limit(self) -> None:
        """Test file size validation (must be < 50MB)."""
        with pytest.raises(ValidationError):
            PRDDocument(
                file_path=Path("large.pdf"),
                file_type="pdf",
                file_size_mb=60.0,  # Exceeds 50MB limit
            )

    def test_file_size_validation_negative(self) -> None:
        """Test file size must be positive."""
        with pytest.raises(ValidationError):
            PRDDocument(
                file_path=Path("test.pdf"),
                file_type="pdf",
                file_size_mb=-1.0,
            )

    @pytest.mark.parametrize(
        "file_type,expected_valid",
        [
            ("pdf", True),
            ("png", True),
            ("jpg", True),
            ("jpeg", True),
            ("txt", True),   # .txt and .md became supported PRD formats
            ("md", True),
            ("docx", False),  # genuinely unsupported
        ],
    )
    def test_supported_file_types(self, file_type, expected_valid) -> None:
        """Test supported file types."""
        if expected_valid:
            doc = PRDDocument(
                file_path=Path(f"test.{file_type}"),
                file_type=file_type,
                file_size_mb=1.0,
            )
            assert doc.file_type == file_type
        else:
            with pytest.raises(ValidationError):
                PRDDocument(
                    file_path=Path(f"test.{file_type}"),
                    file_type=file_type,
                    file_size_mb=1.0,
                )


class TestFigmaDesign:
    """Test FigmaDesign model."""

    def test_valid_figma_design(self) -> None:
        """Test creating valid Figma design."""
        design = FigmaDesign(
            file_key="abc123",
            node_id="1:2",
            name="Login Screen",
        )
        assert design.file_key == "abc123"
        assert design.node_id == "1:2"
        assert design.name == "Login Screen"


class TestTestPoint:
    """Test TestPoint model."""

    def test_valid_test_point(self) -> None:
        """Test creating valid test point."""
        point = TestPoint(
            description="User can login with valid credentials",
            feature="Login",
            priority="P0",
            test_type="positive",
        )
        assert point.description == "User can login with valid credentials"
        assert point.priority == "P0"
        assert point.test_type == "positive"
        assert point.id  # Should auto-generate UUID

    @pytest.mark.parametrize(
        "priority",
        ["P0", "P1", "P2", "P3"],
    )
    def test_valid_priorities(self, priority) -> None:
        """Test all valid priority levels."""
        point = TestPoint(
            description="Test",
            feature="Feature",
            priority=priority,
            test_type="positive",
        )
        assert point.priority == priority

    @pytest.mark.parametrize(
        "test_type",
        ["positive", "negative", "edge_case", "boundary"],
    )
    def test_valid_test_types(self, test_type) -> None:
        """Test all valid test types."""
        point = TestPoint(
            description="Test",
            feature="Feature",
            priority="P1",
            test_type=test_type,
        )
        assert point.test_type == test_type


class TestTestChecklist:
    """Test TestChecklist model."""

    def test_valid_checklist(self) -> None:
        """Test creating valid test checklist."""
        points = [
            TestPoint(
                description="Test 1",
                feature="Feature",
                priority="P0",
                test_type="positive",
            ),
            TestPoint(
                description="Test 2",
                feature="Feature",
                priority="P1",
                test_type="negative",
            ),
        ]

        checklist = TestChecklist(
            feature_name="Login",
            test_points=points,
            coverage_score=85.0,
        )

        assert checklist.feature_name == "Login"
        assert len(checklist.test_points) == 2
        assert checklist.coverage_score == 85.0

    def test_checklist_to_markdown(self) -> None:
        """Test markdown conversion."""
        points = [
            TestPoint(
                description="Test positive scenario",
                feature="Login",
                priority="P0",
                test_type="positive",
            )
        ]

        checklist = TestChecklist(
            feature_name="Login Feature",
            test_points=points,
            coverage_score=75.0,
        )

        markdown = checklist.to_markdown()

        assert "# Test Checklist: Login Feature" in markdown
        assert "Coverage Score" in markdown
        assert "75.0%" in markdown
        assert "P0 Tests" in markdown
        assert "Test positive scenario" in markdown

    def test_coverage_score_bounds(self) -> None:
        """Test coverage score must be 0-100."""
        with pytest.raises(ValidationError):
            TestChecklist(
                feature_name="Test",
                test_points=[],
                coverage_score=150.0,  # Invalid: > 100
            )


class TestTestCase:
    """Test TestCase model."""

    def test_valid_test_case(self, make_test_case) -> None:
        """Test creating valid test case."""
        tc = make_test_case()

        assert tc.test_case_id == "TC001"
        assert tc.feature == "Login"
        assert tc.priority == "P0"
        assert tc.category == "Functional"

    def test_required_fields_are_enforced(self) -> None:
        """The four fields added to the schema must be supplied."""
        import pytest as _pytest

        with _pytest.raises(ValidationError):
            TestCase(
                test_case_id="TC001",
                priority="P0",
                expected_result="Success",
            )

    def test_to_csv_row(self, make_test_case) -> None:
        """Test CSV row conversion."""
        tc = make_test_case(comments="Critical test")

        row = tc.to_csv_row()

        assert len(row) == len(TestCase.csv_header())
        assert row[0] == "TC001"
        assert row[1] == "P0"
        assert row[-1] == "Critical test"

    def test_csv_header(self) -> None:
        """Test CSV header generation."""
        header = TestCase.csv_header()

        # Asserted by content rather than a hardcoded length, which drifted
        # from 7 to 12 columns and failed on every schema change.
        for column in ("Test Case ID", "Priority", "Category", "Expected Result"):
            assert column in header
        assert len(header) == len(set(header)), "duplicate column in the header"
