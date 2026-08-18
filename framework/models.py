"""Pydantic data models for PRD-to-Figma test case generator."""

import uuid
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator


# =============================================================================
# Test Generation Mode
# =============================================================================

class TestGenerationMode(str, Enum):
    """Mode for test case generation."""
    FRONTEND = "frontend"
    BACKEND = "backend"
    BOTH = "both"


# =============================================================================
# Backend Test Models (API, Database, Security, Performance)
# =============================================================================

class BackendTestPoint(BaseModel):
    """Individual backend test point from analysis."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    category: str = Field(..., description="High-level category (e.g., Profile Creation, Security)")
    subcategory: str = Field(..., description="Specific area (e.g., Validation, DB Record)")
    api_component: str = Field(default="", description="API endpoint or component (e.g., POST /users/relationship)")
    test_scenario: str = Field(..., description="What to verify - must start with 'Verify that...'")
    precondition: str = Field(..., description="Setup required before test")
    verification_method: str = Field(..., description="How to test (Call API, Query database, Check config)")
    expected_result: str = Field(..., description="Success criteria")
    priority: Literal["P0", "P1", "P2"] = Field(..., description="Test priority level")
    test_type: Literal[
        "API", "Database", "Security", "Performance",
        "Config", "Analytics", "Backend", "Cache"
    ] = Field(..., description="Type of backend test")

    @model_validator(mode="after")
    def derive_api_component(self):
        """Derive api_component from test_type if empty."""
        if self.api_component and self.api_component.strip():
            return self

        test_type = self.test_type
        category = self.category
        verification_method = self.verification_method

        # Derive from test_type
        if test_type == "Database":
            self.api_component = "Database"
        elif test_type == "Security":
            self.api_component = "Security Module"
        elif test_type == "Performance":
            self.api_component = "Performance Monitor"
        elif test_type == "Config":
            self.api_component = "Configuration"
        elif test_type == "Analytics":
            self.api_component = "Analytics Service"
        elif test_type == "Cache":
            self.api_component = "Cache Layer"
        elif "API" in verification_method.upper() or "CALL" in verification_method.upper():
            self.api_component = f"API - {category}" if category else "API Endpoint"
        elif category:
            self.api_component = f"{test_type} - {category}"
        else:
            self.api_component = test_type or "Backend Component"

        return self


class BackendTestCase(BaseModel):
    """Detailed backend test case matching professional QA format for APIs."""

    # Core identification
    test_case_id: str = Field(..., description="Unique test case ID (e.g., TC_API_PC_001)")
    category: str = Field(..., description="High-level category (e.g., Profile Creation, Security)")
    subcategory: str = Field(..., description="Specific area (e.g., Validation, DB Record, Report Header)")
    api_component: str = Field(default="", description="API endpoint or component (e.g., POST /contacts/link)")

    # Test definition
    test_scenario: str = Field(..., description="Test scenario - must start with 'Verify that...'")
    precondition: str = Field(..., description="Setup required before test (e.g., Valid auth token, existing profile)")
    verification_method: str = Field(..., description="How to test (Call API, Query database, Check config)")
    expected_result: str = Field(..., description="Success criteria (e.g., 400 Bad Request with validation error)")

    # Classification
    priority: Literal["P0", "P1", "P2"] = Field(..., description="Test priority: P0=Critical, P1=High, P2=Medium")
    test_type: Literal[
        "API", "Database", "Security", "Performance",
        "Config", "Analytics", "Backend", "Cache"
    ] = Field(..., description="Type of backend test")

    # Tracking columns (for manual QA workflow)
    dev_status: str = Field(default="", description="Development status (e.g., Not Started, In Progress, Done)")
    qa_status: str = Field(default="", description="QA status (e.g., Not Tested, Pass, Fail, Blocked)")
    comments: str = Field(default="", description="Additional comments or notes")

    @model_validator(mode="after")
    def ensure_api_component(self):
        """Ensure api_component is not empty by deriving from other fields."""
        if self.api_component and self.api_component.strip():
            return self

        test_type = self.test_type
        category = self.category
        verification_method = self.verification_method

        # Derive from test_type
        if test_type == "Database":
            self.api_component = "Database"
        elif test_type == "Security":
            self.api_component = "Security Module"
        elif test_type == "Performance":
            self.api_component = "Performance Monitor"
        elif test_type == "Config":
            self.api_component = "Configuration"
        elif test_type == "Analytics":
            self.api_component = "Analytics Service"
        elif test_type == "Cache":
            self.api_component = "Cache Layer"
        elif "API" in verification_method.upper() or "CALL" in verification_method.upper():
            self.api_component = f"API - {category}" if category else "API Endpoint"
        elif category:
            self.api_component = f"{test_type} - {category}"
        else:
            self.api_component = test_type or "Backend Component"

        return self

    def to_csv_row(self) -> List[str]:
        """Convert backend test case to CSV row format."""
        return [
            self.test_case_id,
            self.category,
            self.subcategory,
            self.api_component,
            self.test_scenario,
            self.precondition,
            self.verification_method,
            self.expected_result,
            self.priority,
            self.test_type,
            self.dev_status,
            self.qa_status,
            self.comments,
        ]

    @staticmethod
    def csv_header() -> List[str]:
        """Get CSV header row for backend tests."""
        return [
            "Test Case ID",
            "Category",
            "Subcategory",
            "API/Component",
            "Test Scenario",
            "Precondition",
            "Verification Method",
            "Expected Result",
            "Priority",
            "Test Type",
            "DEV Status",
            "QA Status",
            "Comments",
        ]


class BackendTestChecklist(BaseModel):
    """Structured backend test checklist output."""

    feature_name: str = Field(..., description="Name of the feature under test")
    test_points: List[BackendTestPoint] = Field(
        default_factory=list, description="List of backend test points"
    )
    coverage_score: float = Field(
        ge=0, le=100, description="Estimated test coverage percentage"
    )
    generated_at: datetime = Field(default_factory=datetime.now)
    needs_more_info: bool = Field(
        default=False, description="Whether more information is needed"
    )
    error_message: Optional[str] = Field(
        None, description="Error or clarification message if needs_more_info is True"
    )

    # Statistics
    api_test_count: int = Field(default=0, description="Number of API tests")
    database_test_count: int = Field(default=0, description="Number of database tests")
    security_test_count: int = Field(default=0, description="Number of security tests")
    performance_test_count: int = Field(default=0, description="Number of performance tests")

    def to_markdown(self) -> str:
        """Convert checklist to markdown format."""
        lines = [
            f"# Backend Test Checklist: {self.feature_name}",
            "",
            f"**Generated**: {self.generated_at.strftime('%Y-%m-%d %H:%M:%S')}",
            f"**Coverage Score**: {self.coverage_score:.1f}%",
            "",
            f"**API Tests**: {self.api_test_count} | **DB Tests**: {self.database_test_count} | "
            f"**Security Tests**: {self.security_test_count} | **Performance Tests**: {self.performance_test_count}",
            "",
            "## Test Points",
            "",
        ]

        # Group by category
        categories = set(p.category for p in self.test_points)
        for category in sorted(categories):
            points = [p for p in self.test_points if p.category == category]
            if points:
                lines.append(f"### {category}")
                lines.append("")
                for point in points:
                    lines.append(
                        f"- [ ] **[{point.test_type}]** {point.test_scenario} "
                        f"({point.api_component}) - {point.priority}"
                    )
                lines.append("")

        return "\n".join(lines)


class PRDDocument(BaseModel):
    """PRD document model with validation."""

    model_config = ConfigDict(validate_assignment=True)

    file_path: Path
    file_type: Literal["pdf", "png", "jpg", "jpeg", "txt", "md"]
    uploaded_at: datetime = Field(default_factory=datetime.now)
    file_size_mb: float = Field(gt=0, lt=50, description="File size in MB, max 50MB")
    content: Optional[str] = Field(
        None, description="Extracted text content from document"
    )
    images: List[Path] = Field(default_factory=list, description="Extracted images")


class FigmaNode(BaseModel):
    """Figma node/frame model."""

    node_id: str = Field(..., description="Figma node ID (e.g., '1:2')")
    name: str = Field(..., description="Node/frame name")
    type: str = Field(..., description="Node type (FRAME, GROUP, etc.)")
    screenshot_url: Optional[HttpUrl] = Field(
        None, description="Screenshot download URL"
    )


class FigmaDesign(BaseModel):
    """Figma design document model."""

    file_key: str = Field(..., description="Figma file key")
    node_id: str = Field(..., description="Figma node ID")
    name: str = Field(..., description="Design name")
    screenshot_path: Optional[Path] = Field(
        None, description="Local path to downloaded screenshot"
    )
    imported_at: datetime = Field(default_factory=datetime.now)


class TestPoint(BaseModel):
    """Individual test point from analysis."""

    # Names beginning with "Test" make pytest try to collect these as test
    # classes and warn on every run. They are models, not tests.
    __test__ = False

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    description: str = Field(..., description="Test point description")
    feature: str = Field(..., description="Feature being tested")
    priority: Literal["P0", "P1", "P2", "P3"] = Field(
        ..., description="Test priority level"
    )
    test_type: Literal[
        # Frontend test types
        "positive", "negative", "edge_case", "boundary", "user_journey",
        "subscription_state", "navigation", "ui_compliance", "data_sync",
        "state_propagation", "feature_gating",
        # Backend test types
        "API", "Database", "Security", "Performance", "Config", "Analytics",
        "Backend", "Cache", "api", "database", "security", "performance"
    ] = Field(
        ..., description="Type of test scenario"
    )
    screenshot_url: Optional[str] = Field(
        None, description="URL to Figma screenshot for this test point"
    )
    screens: Optional[List[str]] = Field(
        default_factory=list, description="List of screen names for user journey tests"
    )


class FeatureCoverage(BaseModel):
    """Coverage breakdown for a specific feature."""

    feature: str = Field(..., description="Feature name")
    coverage_percentage: float = Field(
        ge=0, le=100, description="Coverage percentage for this feature"
    )
    test_count: int = Field(ge=0, description="Number of tests for this feature")
    missing_scenarios: List[str] = Field(
        default_factory=list, description="Missing test scenarios"
    )
    risk_level: Literal["high", "medium", "low"] = Field(
        ..., description="Risk level based on coverage"
    )


class TestTypeDistribution(BaseModel):
    """Distribution of test types."""

    # Names beginning with "Test" make pytest try to collect these as test
    # classes and warn on every run. They are models, not tests.
    __test__ = False

    positive: int = Field(ge=0, description="Number of positive test cases")
    negative: int = Field(ge=0, description="Number of negative test cases")
    boundary: int = Field(ge=0, description="Number of boundary test cases")
    edge_case: int = Field(ge=0, description="Number of edge case test cases")
    user_journey: int = Field(ge=0, default=0, description="Number of user journey test cases")

    @property
    def total(self) -> int:
        """Get total number of tests."""
        return self.positive + self.negative + self.boundary + self.edge_case + self.user_journey

    def get_percentage(self, test_type: str) -> float:
        """Get percentage for a test type."""
        if self.total == 0:
            return 0.0
        count = getattr(self, test_type, 0)
        return (count / self.total) * 100


class RiskAssessment(BaseModel):
    """Risk assessment for test coverage."""

    high_risk_features: List[str] = Field(
        default_factory=list,
        description="Features with critical coverage gaps (P0 missing or <30% coverage)",
    )
    medium_risk_features: List[str] = Field(
        default_factory=list,
        description="Features with moderate coverage gaps (30-70% coverage)",
    )
    low_risk_features: List[str] = Field(
        default_factory=list, description="Features with good coverage (>70%)"
    )


class CoverageAnalysis(BaseModel):
    """Comprehensive coverage analysis."""

    feature_coverage: List[FeatureCoverage] = Field(
        default_factory=list, description="Coverage breakdown by feature"
    )
    test_type_distribution: TestTypeDistribution = Field(
        ..., description="Distribution of test types"
    )
    missing_scenarios: List[str] = Field(
        default_factory=list,
        description="Overall missing test scenarios detected by AI",
    )
    risk_assessment: RiskAssessment = Field(
        ..., description="Risk assessment based on coverage gaps"
    )
    recommendations: List[str] = Field(
        default_factory=list, description="AI-generated recommendations for improvement"
    )


class TruthTableEntry(BaseModel):
    """Truth Table / Test Matrix entry for navigation and state transition flows.

    Used for testing screen-to-screen navigation, payment redirections,
    subscription state changes, and other multi-outcome flows.
    """

    # Unique identifier
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))

    # Core columns matching user's spreadsheet format
    screen: str = Field(..., description="Starting screen (e.g., SideBar, Home Screen, Wallet)")
    checkpoint: str = Field(
        ...,
        description="Navigation path (e.g., 'Home -> Tap Subscribe CTA -> Subscription Page')"
    )

    # Redirection outcomes for different states
    failed_redirect: str = Field(
        ...,
        description="Where it redirects on failure (e.g., 'Home Screen (with error toast)')"
    )
    pending_redirect: str = Field(
        ...,
        description="Where it redirects when pending (e.g., 'Loading Screen')"
    )
    successful_redirect: str = Field(
        ...,
        description="Where it redirects on success (e.g., 'Subscription Page')"
    )

    # Auto-redirection status for each state
    auto_redirect_failed: Literal["Pass", "NA"] = Field(
        default="NA", description="Whether auto-redirect works on failure"
    )
    auto_redirect_pending: Literal["Pass", "NA"] = Field(
        default="NA", description="Whether auto-redirect works when pending"
    )
    auto_redirect_success: Literal["Pass", "NA"] = Field(
        default="Pass", description="Whether auto-redirect works on success"
    )

    # Testing status
    result: Literal["Pass", "Failed", "Not Tested"] = Field(
        default="Not Tested", description="Test execution result"
    )
    expected: str = Field(..., description="Expected behavior description")

    # Metadata
    feature: str = Field(..., description="Feature being tested")
    priority: Literal["P0", "P1", "P2"] = Field(
        default="P1", description="Test priority"
    )
    test_type: Literal["navigation", "payment_redirect", "state_transition", "deep_link"] = Field(
        default="navigation", description="Type of truth table test"
    )

    def to_csv_row(self) -> List[str]:
        """Convert truth table entry to CSV row format."""
        return [
            self.screen,
            self.checkpoint,
            self.failed_redirect,
            self.pending_redirect,
            self.successful_redirect,
            self.auto_redirect_failed,
            self.auto_redirect_pending,
            self.auto_redirect_success,
            self.result,
            self.expected,
            self.feature,
            self.priority,
            self.test_type,
        ]

    @staticmethod
    def csv_header() -> List[str]:
        """Get CSV header row for truth table."""
        return [
            "Screen",
            "CheckPoint",
            "Failed (Redirected To)",
            "Pending (Redirected To)",
            "Successful (Redirected To)",
            "Auto Redirection (Failed)",
            "Auto Redirection (Pending)",
            "Auto Redirection (Successful)",
            "Results",
            "Expected",
            "Feature",
            "Priority",
            "Test Type",
        ]


class TestChecklist(BaseModel):
    """Structured test checklist output."""

    # Names beginning with "Test" make pytest try to collect these as test
    # classes and warn on every run. They are models, not tests.
    __test__ = False

    feature_name: str = Field(..., description="Name of the feature under test")
    test_points: List[TestPoint] = Field(
        default_factory=list, description="List of test points"
    )
    coverage_score: float = Field(
        ge=0, le=100, description="Estimated test coverage percentage"
    )
    generated_at: datetime = Field(default_factory=datetime.now)
    needs_more_info: bool = Field(
        default=False, description="Whether more information is needed"
    )
    error_message: Optional[str] = Field(
        None, description="Error or clarification message if needs_more_info is True"
    )
    coverage_analysis: Optional[CoverageAnalysis] = Field(
        None, description="Detailed coverage analysis and insights"
    )

    # Truth Table entries for navigation/state flows
    truth_table_entries: List[TruthTableEntry] = Field(
        default_factory=list,
        description="Truth table entries for navigation and state transition testing"
    )
    truth_table_features: List[str] = Field(
        default_factory=list,
        description="List of features that have truth table format tests"
    )

    def to_markdown(self) -> str:
        """Convert checklist to markdown format.

        Returns:
            Markdown formatted checklist string.
        """
        lines = [
            f"# Test Checklist: {self.feature_name}",
            "",
            f"**Generated**: {self.generated_at.strftime('%Y-%m-%d %H:%M:%S')}",
            f"**Coverage Score**: {self.coverage_score:.1f}%",
            "",
            "## Test Points",
            "",
        ]

        # Group by priority
        for priority in ["P0", "P1", "P2", "P3"]:
            points = [p for p in self.test_points if p.priority == priority]
            if points:
                lines.append(f"### {priority} Tests")
                lines.append("")
                for point in points:
                    lines.append(
                        f"- [ ] **[{point.test_type}]** {point.description} ({point.feature})"
                    )
                lines.append("")

        return "\n".join(lines)


class TestCase(BaseModel):
    """Detailed test case model matching professional QA format."""

    # Names beginning with "Test" make pytest try to collect these as test
    # classes and warn on every run. They are models, not tests.
    __test__ = False

    # Core identification
    test_case_id: str = Field(..., description="Unique test case ID (e.g., TC_UI_NU_001)")
    priority: Literal["P0", "P1", "P2"] = Field(
        ..., description="Test priority: P0=Critical, P1=High, P2=Medium"
    )
    category: str = Field(
        ..., description="Major category (e.g., New User Flows, Profile Creation, Subscription States)"
    )
    user_type: str = Field(
        default="Any", description="User type: New User, Existing User, Free User, Subscribed User, Any"
    )

    # Context fields
    screen_reference: str = Field(
        ..., description="Screen/location in app (e.g., Home page, Switch Profile bottom sheet)"
    )
    precondition: str = Field(
        ..., description="Required state before test (include subscription status if applicable)"
    )

    # Test definition - MUST start with 'Verify that...'
    test_scenario: str = Field(
        ..., description="Test scenario description - MUST start with 'Verify that...'"
    )
    steps_to_execute: str = Field(
        ..., description="Numbered test steps (e.g., 1. Tap Avatar 2. Observe profile list)"
    )
    expected_result: str = Field(..., description="Specific expected outcome")

    # Status tracking
    dev_status: Literal["Not Started", "In Progress", "Done"] = Field(
        default="Not Started", description="Development status"
    )
    qa_status: Literal["Not Started", "Passed", "Failed", "Blocked", "Not Ready"] = Field(
        default="Not Started", description="QA testing status"
    )
    comments: str = Field(default="", description="Additional comments or notes")

    # Legacy/compatibility fields
    feature: str = Field(default="", description="Feature being tested (for backward compatibility)")
    screenshot_url: Optional[str] = Field(
        None, description="URL to Figma screenshot showing the screen being tested"
    )
    test_type: Optional[Literal[
        "positive", "negative", "edge_case", "boundary", "user_journey",
        "subscription_state", "navigation", "ui_compliance", "data_sync",
        "state_propagation", "feature_gating"
    ]] = Field(
        None, description="Type of test scenario"
    )

    # Backward compatibility properties (aliases for old field names)
    @property
    def requirement_description(self) -> str:
        """Alias for test_scenario (backward compatibility)."""
        return self.test_scenario

    @property
    def test_step(self) -> str:
        """Alias for steps_to_execute (backward compatibility)."""
        return self.steps_to_execute

    @property
    def notes(self) -> str:
        """Alias for comments (backward compatibility)."""
        return self.comments

    def to_csv_row(self) -> List[str]:
        """Convert test case to CSV row format.

        Returns:
            List of strings representing CSV row values.
        """
        return [
            self.test_case_id,
            self.priority,
            self.category,
            self.user_type,
            self.screen_reference,
            self.precondition,
            self.test_scenario,
            self.steps_to_execute,
            self.expected_result,
            self.dev_status,
            self.qa_status,
            self.comments,
        ]

    @staticmethod
    def csv_header() -> List[str]:
        """Get CSV header row.

        Returns:
            List of column names.
        """
        return [
            "Test Case ID",
            "Priority",
            "Category",
            "User Type",
            "Screen Reference",
            "Precondition",
            "Test Scenario",
            "Steps to Execute",
            "Expected Result",
            "Dev Status",
            "QA Status",
            "Comments",
        ]


class TestAnalysisRequest(BaseModel):
    """Request model for test analysis."""

    # Names beginning with "Test" make pytest try to collect these as test
    # classes and warn on every run. They are models, not tests.
    __test__ = False

    prd_content: str = Field(..., description="PRD text content")
    images: List[Path] = Field(default_factory=list, description="Associated images")
    feature_name: Optional[str] = Field(None, description="Optional feature name")
    apply_methods: List[str] = Field(
        default_factory=lambda: [
            "equivalence_partitioning",
            "boundary_value_analysis",
            "decision_tables",
            "scenario_method",
            "state_transition",
            "error_guessing",
        ],
        description="Test design methods to apply",
    )


class TestAnalysisResponse(BaseModel):
    """Response model for test analysis."""

    checklist: TestChecklist
    analysis_time_seconds: float
    methods_applied: List[str]
    metadata: dict = Field(default_factory=dict)
