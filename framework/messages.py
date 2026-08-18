"""
Centralized messaging system for the PRD/Figma Test Generator.

This module provides consistent, icon-free messages that can be enhanced
with icons on the frontend. All user-facing messages should be defined here
to maintain consistency and enable easy updates.

Icon identifiers (used by frontend to render lucide-react icons):
- ROCKET: Start/launch actions
- CHECK: Success/completion
- ALERT: Warnings
- INFO: Information
- CHART: Analytics/stats
- LIGHTBULB: Tips/suggestions
"""

from typing import Dict, Any


class StreamMessages:
    """Messages for streaming analysis flow"""

    # Analysis start messages
    STARTING_COMBINED = "[ROCKET] Starting combined Figma + PRD analysis..."
    STARTING_FIGMA = "[ROCKET] Starting Figma design analysis..."
    STARTING_PRD = "[ROCKET] Starting PRD analysis..."
    STARTING_GENERIC = "[ROCKET] Starting analysis..."

    # Progress messages
    EXTRACTING_FIGMA = "[INFO] Extracting Figma design data..."
    ANALYZING_REQUIREMENTS = "[INFO] Analyzing requirements..."
    GENERATING_TEST_POINTS = "[INFO] Generating test points..."
    EXPANDING_TEST_CASES = "[INFO] Expanding test cases..."
    CALCULATING_COVERAGE = "[CHART] Calculating coverage metrics..."

    # Success messages
    DESIGN_RECEIVED = "[CHECK] Design data received successfully!"
    ANALYSIS_COMPLETE = "[CHECK] AI analysis complete! Processing results..."
    TEST_GENERATION_COMPLETE = "[CHECK] Test generation complete!"

    # Error messages
    ANALYSIS_FAILED = "[ALERT] Analysis failed. Please try again."
    INVALID_INPUT = "[ALERT] Invalid input provided."
    RATE_LIMIT_HIT = "[ALERT] API rate limit reached. Retrying..."


class StatusMessages:
    """General status messages"""

    PROCESSING = "[INFO] Processing..."
    VALIDATING = "[INFO] Validating input..."
    SAVING_RESULTS = "[INFO] Saving results..."
    READY = "[CHECK] Ready!"
    ERROR = "[ALERT] An error occurred."


class InfoMessages:
    """Informational tips and suggestions"""

    FIGMA_URL_TIP = (
        "[LIGHTBULB] Paste your Figma design URL to generate UI-focused test cases"
    )
    PRD_TEXT_TIP = "[LIGHTBULB] Describe your feature requirements in detail for comprehensive test coverage"
    COMBINED_INPUT_TIP = (
        "[LIGHTBULB] Combine Figma design + PRD for maximum test coverage"
    )
    STREAMING_MODE_TIP = "[INFO] Real-time streaming mode provides instant feedback as tests are generated"


def format_progress_message(current: int, total: int, item_type: str = "items") -> str:
    """
    Format a progress message with icon identifier.

    Args:
        current: Current progress count
        total: Total items count
        item_type: Type of items being processed

    Returns:
        Formatted message with INFO icon identifier
    """
    percentage = int((current / total) * 100) if total > 0 else 0
    return f"[INFO] Processing {item_type}: {current}/{total} ({percentage}%)"


def format_test_case_message(test_case_num: int, feature: str) -> str:
    """
    Format a message for a generated test case.

    Args:
        test_case_num: Test case number
        feature: Feature name

    Returns:
        Formatted message with CHECK icon identifier
    """
    return f"[CHECK] Generated test case #{test_case_num}: {feature}"


def format_coverage_message(coverage_score: float) -> str:
    """
    Format a coverage score message.

    Args:
        coverage_score: Coverage score (0-100)

    Returns:
        Formatted message with CHART icon identifier
    """
    return f"[CHART] Test coverage: {coverage_score:.1f}%"


def get_message_with_data(template: str, **kwargs) -> Dict[str, Any]:
    """
    Create a message dict with icon identifier and optional data.

    Args:
        template: Message template with [ICON] identifier
        **kwargs: Additional data to include

    Returns:
        Dict with 'message' and optional data fields
    """
    result = {"message": template}
    result.update(kwargs)
    return result
