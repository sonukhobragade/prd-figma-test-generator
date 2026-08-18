"""Tests for framework.test_expander module."""

import csv
from pathlib import Path

import pytest

from framework.models import TestCase, TestChecklist, TestPoint
from framework.test_expander import TestCaseExpander, TestExpanderError


@pytest.fixture
def expander():
    """Create TestCaseExpander instance."""
    return TestCaseExpander()


@pytest.fixture
def sample_test_point():
    """Create sample test point for testing."""
    return TestPoint(
        id="TP001",
        description="User can login with valid credentials",
        feature="Login",
        priority="P0",
        test_type="positive",
    )


@pytest.fixture
def sample_checklist():
    """Create sample test checklist with multiple test points."""
    test_points = [
        TestPoint(
            id="TP001",
            description="User can login with valid credentials",
            feature="Login",
            priority="P0",
            test_type="positive",
        ),
        TestPoint(
            id="TP002",
            description="User sees error with invalid credentials",
            feature="Login",
            priority="P0",
            test_type="negative",
        ),
        TestPoint(
            id="TP003",
            description="Password field accepts maximum 128 characters",
            feature="Login",
            priority="P1",
            test_type="boundary",
        ),
        TestPoint(
            id="TP004",
            description="Login with special characters in username",
            feature="Login",
            priority="P2",
            test_type="edge_case",
        ),
    ]
    return TestChecklist(
        feature_name="Login System",
        test_points=test_points,
        coverage_score=85.5,
    )


class TestTestCaseExpander:
    """Tests for TestCaseExpander class."""

    def test_initialization(self, expander):
        """Test expander initialization."""
        assert expander.test_case_counter == 1

    def test_generate_test_case_id_basic(self, expander):
        """IDs are TC_UI_<CAT>_<NUM>_<HASH>; the old TC001_P0_Login shape,
        which embedded the priority and feature name, is gone."""
        test_id = expander._generate_test_case_id("P0", "Login", "navigation", "tap login")
        assert test_id.startswith("TC_UI_NAV_001")
        assert expander.test_case_counter == 2

    def test_generate_test_case_id_increments(self, expander):
        """The counter advances regardless of category."""
        first_id = expander._generate_test_case_id("P0", "Login", "positive", "valid login")
        second_id = expander._generate_test_case_id("P1", "Signup", "negative", "bad email")
        assert "_001_" in first_id
        assert "_002_" in second_id
        assert expander.test_case_counter == 3

    def test_ids_are_unique_for_different_scenarios(self, expander):
        """The trailing hash is derived from the scenario, so two points in
        the same category do not collide."""
        a = expander._generate_test_case_id("P0", "Login", "positive", "valid login")
        b = expander._generate_test_case_id("P0", "Login", "positive", "logout then login")
        assert a != b

    def test_feature_name_no_longer_leaks_into_the_id(self, expander):
        """Punctuation in the feature name used to be escaped into the id;
        the category code replaced it, so nothing needs sanitising."""
        test_id = expander._generate_test_case_id("P0", "User Login & Auth!", "positive", "x")
        assert "Auth" not in test_id
        assert test_id.startswith("TC_UI_")

    def test_generate_test_case_id_truncates_long_names(self, expander):
        """Test that long feature names are truncated."""
        long_name = "This is a very long feature name that should be truncated"
        test_id = expander._generate_test_case_id("P0", long_name)
        # Should be truncated to 20 chars
        feature_part = test_id.split("_", 2)[2]
        assert len(feature_part) <= 20


class TestGenerateTestSteps:
    """Tests for generate_test_steps method."""

    def test_positive_test_steps(self, expander, sample_test_point):
        """Test generation of positive test steps."""
        steps = expander.generate_test_steps(sample_test_point)
        assert "1. " in steps
        assert "2. " in steps
        assert "3. " in steps
        assert sample_test_point.description in steps
        assert sample_test_point.feature in steps

    def test_negative_test_steps_with_setup(self, expander):
        """Test generation of negative test steps with setup."""
        test_point = TestPoint(
            id="TP002",
            description="Invalid phone number shows error",
            feature="Phone Validation",
            priority="P0",
            test_type="negative",
        )
        steps = expander.generate_test_steps(test_point, include_setup=True)
        assert "Setup:" in steps
        assert "error" in steps.lower()
        assert test_point.description in steps

    def test_negative_test_steps_without_setup(self, expander):
        """Test generation of negative test steps without setup."""
        test_point = TestPoint(
            id="TP002",
            description="Invalid phone number shows error",
            feature="Phone Validation",
            priority="P0",
            test_type="negative",
        )
        steps = expander.generate_test_steps(test_point, include_setup=False)
        assert "Setup:" not in steps
        assert "error" in steps.lower()

    def test_boundary_test_steps(self, expander):
        """Test generation of boundary test steps."""
        test_point = TestPoint(
            id="TP003",
            description="Test min and max password length",
            feature="Password Field",
            priority="P1",
            test_type="boundary",
        )
        steps = expander.generate_test_steps(test_point)
        assert "minimum" in steps.lower()
        assert "maximum" in steps.lower()
        assert "boundary" in steps.lower() or "limit" in steps.lower()

    def test_edge_case_test_steps(self, expander):
        """Test generation of edge case test steps."""
        test_point = TestPoint(
            id="TP004",
            description="Special characters in username",
            feature="Username Input",
            priority="P2",
            test_type="edge_case",
        )
        steps = expander.generate_test_steps(test_point, include_setup=True)
        assert "edge" in steps.lower() or "unusual" in steps.lower()
        assert test_point.description in steps

    def test_all_test_types_covered(self, expander):
        """Test that all test types generate steps."""
        test_types = ["positive", "negative", "boundary", "edge_case"]
        for test_type in test_types:
            test_point = TestPoint(
                id="TP005",
                description="Test description",
                feature="Feature",
                priority="P2",
                test_type=test_type,
            )
            steps = expander.generate_test_steps(test_point)
            assert steps  # Should generate non-empty steps
            assert test_point.description in steps or test_point.feature in steps


class TestGenerateExpectedResult:
    """Tests for _generate_expected_result method."""

    def test_positive_expected_result(self, expander):
        """Test expected result for positive test."""
        test_point = TestPoint(
            id="TP001",
            description="Login succeeds",
            feature="Login",
            priority="P0",
            test_type="positive",
        )
        result = expander._generate_expected_result(test_point)
        assert "✓" in result
        assert "successfully" in result.lower()
        assert test_point.feature in result

    def test_negative_expected_result(self, expander):
        """Test expected result for negative test."""
        test_point = TestPoint(
            id="TP002",
            description="Invalid input rejected",
            feature="Validation",
            priority="P0",
            test_type="negative",
        )
        result = expander._generate_expected_result(test_point)
        assert "✓" in result
        assert "error" in result.lower() or "reject" in result.lower()
        assert "stable" in result.lower()

    def test_boundary_expected_result(self, expander):
        """Test expected result for boundary test."""
        test_point = TestPoint(
            id="TP003",
            description="Test length limits",
            feature="Input Field",
            priority="P1",
            test_type="boundary",
        )
        result = expander._generate_expected_result(test_point)
        assert "✓" in result
        assert "boundary" in result.lower() or "limit" in result.lower()

    def test_edge_case_expected_result(self, expander):
        """Test expected result for edge case test."""
        test_point = TestPoint(
            id="TP004",
            description="Special characters",
            feature="Input",
            priority="P2",
            test_type="edge_case",
        )
        result = expander._generate_expected_result(test_point)
        assert "✓" in result
        assert "edge" in result.lower() or "integrity" in result.lower()


class TestGenerateNotes:
    """Tests for _generate_notes method."""

    def test_notes_for_p0_priority(self, expander):
        """Test notes include CRITICAL for P0 priority."""
        test_point = TestPoint(
            id="TP001",
            description="Critical test",
            feature="Feature",
            priority="P0",
            test_type="positive",
        )
        notes = expander._generate_notes(test_point)
        assert "CRITICAL" in notes

    def test_notes_for_p1_priority(self, expander):
        """Test notes include HIGH PRIORITY for P1."""
        test_point = TestPoint(
            id="TP001",
            description="Important test",
            feature="Feature",
            priority="P1",
            test_type="positive",
        )
        notes = expander._generate_notes(test_point)
        assert "HIGH PRIORITY" in notes

    def test_notes_for_lower_priorities(self, expander):
        """Test notes for P2 and P3 priorities."""
        for priority in ["P2", "P3"]:
            test_point = TestPoint(
                id="TP001",
                description="Test",
                feature="Feature",
                priority=priority,
                test_type="positive",
            )
            notes = expander._generate_notes(test_point)
            # Should not have CRITICAL or HIGH PRIORITY
            assert "CRITICAL" not in notes
            assert "HIGH PRIORITY" not in notes

    def test_notes_for_negative_test(self, expander):
        """Test notes include error handling info for negative tests."""
        test_point = TestPoint(
            id="TP002",
            description="Test",
            feature="Feature",
            priority="P2",
            test_type="negative",
        )
        notes = expander._generate_notes(test_point)
        assert "error" in notes.lower() or "validation" in notes.lower()

    def test_notes_for_boundary_test(self, expander):
        """Test notes for boundary tests."""
        test_point = TestPoint(
            id="TP003",
            description="Test",
            feature="Feature",
            priority="P2",
            test_type="boundary",
        )
        notes = expander._generate_notes(test_point)
        assert "boundary" in notes.lower() or "minimum" in notes.lower()

    def test_notes_for_edge_case_test(self, expander):
        """Test notes for edge case tests."""
        test_point = TestPoint(
            id="TP004",
            description="Test",
            feature="Feature",
            priority="P2",
            test_type="edge_case",
        )
        notes = expander._generate_notes(test_point)
        assert "edge" in notes.lower() or "unusual" in notes.lower()


class TestExpandTestPoint:
    """Tests for expand_test_point method."""

    def test_expand_test_point_creates_test_case(self, expander, sample_test_point):
        """Test that expand_test_point creates a TestCase."""
        test_case = expander.expand_test_point(sample_test_point)
        assert isinstance(test_case, TestCase)
        assert test_case.feature == sample_test_point.feature
        assert test_case.priority == sample_test_point.priority

    def test_expand_test_point_generates_unique_id(self, expander, sample_test_point):
        """Test that each expansion generates unique ID."""
        test_case1 = expander.expand_test_point(sample_test_point)
        test_case2 = expander.expand_test_point(sample_test_point)
        assert test_case1.test_case_id != test_case2.test_case_id

    def test_expand_test_point_includes_all_fields(self, expander, sample_test_point):
        """Test that test case includes all required fields."""
        test_case = expander.expand_test_point(sample_test_point)
        assert test_case.test_case_id
        assert test_case.feature
        assert test_case.requirement_description
        assert test_case.test_step
        assert test_case.expected_result
        assert test_case.priority
        # Notes can be empty for some test types


class TestExpandChecklist:
    """Tests for expand_checklist method."""

    def test_expand_checklist_basic(self, expander, sample_checklist):
        """Test basic checklist expansion."""
        test_cases = expander.expand_checklist(sample_checklist)
        assert len(test_cases) == len(sample_checklist.test_points)
        assert all(isinstance(tc, TestCase) for tc in test_cases)

    def test_expand_checklist_resets_counter(self, expander, sample_checklist):
        """Test that counter is reset for each checklist."""
        # First expansion
        test_cases1 = expander.expand_checklist(sample_checklist)
        first_id = test_cases1[0].test_case_id

        # Second expansion should reset counter
        test_cases2 = expander.expand_checklist(sample_checklist)
        second_id = test_cases2[0].test_case_id

        assert first_id == second_id  # Both should start with TC001

    def test_expand_empty_checklist(self, expander):
        """Test expanding empty checklist."""
        empty_checklist = TestChecklist(
            feature_name="Empty", test_points=[], coverage_score=0.0
        )
        test_cases = expander.expand_checklist(empty_checklist)
        assert test_cases == []

    def test_expand_checklist_preserves_order(self, expander, sample_checklist):
        """Test that test case order matches test point order."""
        test_cases = expander.expand_checklist(sample_checklist)
        for i, test_point in enumerate(sample_checklist.test_points):
            assert test_cases[i].feature == test_point.feature
            assert test_cases[i].priority == test_point.priority

    def test_expand_checklist_error_handling(self, expander):
        """Test that expansion errors are properly handled."""
        # Create invalid checklist
        invalid_checklist = None
        with pytest.raises(TestExpanderError):
            expander.expand_checklist(invalid_checklist)


class TestExportToCsv:
    """Tests for export_to_csv method."""

    def test_export_to_csv_creates_file(self, expander, sample_checklist, tmp_path):
        """Test that CSV file is created."""
        test_cases = expander.expand_checklist(sample_checklist)
        output_path = tmp_path / "test_cases.csv"

        expander.export_to_csv(test_cases, output_path)

        assert output_path.exists()
        assert output_path.is_file()

    def test_export_to_csv_creates_directory(
        self, expander, sample_checklist, tmp_path
    ):
        """Test that output directory is created if it doesn't exist."""
        test_cases = expander.expand_checklist(sample_checklist)
        output_path = tmp_path / "subdir" / "nested" / "test_cases.csv"

        expander.export_to_csv(test_cases, output_path)

        assert output_path.parent.exists()
        assert output_path.exists()

    def test_export_to_csv_content(self, expander, sample_checklist, tmp_path):
        """Test that CSV content is correct."""
        test_cases = expander.expand_checklist(sample_checklist)
        output_path = tmp_path / "test_cases.csv"

        expander.export_to_csv(test_cases, output_path)

        # Read and verify CSV
        with open(output_path, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            rows = list(reader)

        # Check header
        assert rows[0] == TestCase.csv_header()

        # Check data rows
        assert len(rows) == len(test_cases) + 1  # +1 for header

    def test_export_empty_test_cases(self, expander, tmp_path):
        """Test exporting empty test cases list."""
        output_path = tmp_path / "empty.csv"
        expander.export_to_csv([], output_path)

        assert output_path.exists()
        with open(output_path, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            rows = list(reader)
        # Should only have header
        assert len(rows) == 1

    def test_export_error_handling(self, expander, sample_checklist):
        """Test export error handling."""
        test_cases = expander.expand_checklist(sample_checklist)
        # Invalid path
        invalid_path = Path("/invalid/path/that/does/not/exist/test.csv")

        with pytest.raises(TestExpanderError):
            expander.export_to_csv(test_cases, invalid_path)


class TestGenerateSummaryReport:
    """Tests for generate_summary_report method."""

    def test_summary_report_basic(self, expander, sample_checklist):
        """Test basic summary report generation."""
        test_cases = expander.expand_checklist(sample_checklist)
        summary = expander.generate_summary_report(test_cases)

        assert "total_cases" in summary
        assert "by_priority" in summary
        assert "by_feature" in summary
        assert "by_type" in summary
        assert summary["total_cases"] == len(test_cases)

    def test_summary_report_priority_counts(self, expander, sample_checklist):
        """Test that priority counts are correct."""
        test_cases = expander.expand_checklist(sample_checklist)
        summary = expander.generate_summary_report(test_cases)

        # Count expected priorities from sample_checklist
        p0_count = sum(1 for tp in sample_checklist.test_points if tp.priority == "P0")
        p1_count = sum(1 for tp in sample_checklist.test_points if tp.priority == "P1")
        p2_count = sum(1 for tp in sample_checklist.test_points if tp.priority == "P2")

        assert summary["by_priority"]["P0"] == p0_count
        assert summary["by_priority"]["P1"] == p1_count
        assert summary["by_priority"]["P2"] == p2_count

    def test_summary_report_feature_counts(self, expander, sample_checklist):
        """Test that feature counts are correct."""
        test_cases = expander.expand_checklist(sample_checklist)
        summary = expander.generate_summary_report(test_cases)

        # All sample test points have "Login" feature
        assert "Login" in summary["by_feature"]
        assert summary["by_feature"]["Login"] == len(test_cases)

    def test_summary_report_type_counts(self, expander, sample_checklist):
        """Test that test type estimation works."""
        test_cases = expander.expand_checklist(sample_checklist)
        summary = expander.generate_summary_report(test_cases)

        # Check that types are counted
        type_counts = summary["by_type"]
        assert "positive" in type_counts
        assert "negative" in type_counts
        assert "edge_case" in type_counts
        assert "boundary" in type_counts

        # Total should match total cases
        total_types = sum(type_counts.values())
        assert total_types == len(test_cases)

    def test_summary_report_empty_cases(self, expander):
        """Test summary report with empty test cases."""
        summary = expander.generate_summary_report([])

        assert summary["total_cases"] == 0
        assert summary["by_priority"] == {}
        assert summary["by_feature"] == {}
        assert summary["by_type"] == {}

    def test_summary_report_mixed_features(self, expander):
        """Test summary with multiple features."""
        test_points = [
            TestPoint(
                id="TP001",
                description="Test1",
                feature="Login",
                priority="P0",
                test_type="positive",
            ),
            TestPoint(
                id="TP002",
                description="Test2",
                feature="Signup",
                priority="P1",
                test_type="positive",
            ),
            TestPoint(
                id="TP003",
                description="Test3",
                feature="Login",
                priority="P0",
                test_type="negative",
            ),
        ]
        checklist = TestChecklist(
            feature_name="Mixed", test_points=test_points, coverage_score=80.0
        )

        test_cases = expander.expand_checklist(checklist)
        summary = expander.generate_summary_report(test_cases)

        assert summary["by_feature"]["Login"] == 2
        assert summary["by_feature"]["Signup"] == 1
