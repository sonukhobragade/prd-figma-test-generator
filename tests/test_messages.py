"""Tests for framework.messages module."""


from framework.messages import (
    InfoMessages,
    StatusMessages,
    StreamMessages,
    format_coverage_message,
    format_progress_message,
    format_test_case_message,
    get_message_with_data,
)


class TestStreamMessages:
    """Tests for StreamMessages class."""

    def test_starting_messages_have_rocket_icon(self):
        """Test that all starting messages have ROCKET icon identifier."""
        assert "[ROCKET]" in StreamMessages.STARTING_COMBINED
        assert "[ROCKET]" in StreamMessages.STARTING_FIGMA
        assert "[ROCKET]" in StreamMessages.STARTING_PRD
        assert "[ROCKET]" in StreamMessages.STARTING_GENERIC

    def test_progress_messages_have_info_icon(self):
        """Test that progress messages have INFO icon identifier."""
        assert "[INFO]" in StreamMessages.ANALYZING_REQUIREMENTS
        assert "[INFO]" in StreamMessages.GENERATING_TEST_POINTS
        assert "[INFO]" in StreamMessages.EXPANDING_TEST_CASES

    def test_success_messages_have_check_icon(self):
        """Test that success messages have CHECK icon identifier."""
        assert "[CHECK]" in StreamMessages.DESIGN_RECEIVED
        assert "[CHECK]" in StreamMessages.ANALYSIS_COMPLETE
        assert "[CHECK]" in StreamMessages.TEST_GENERATION_COMPLETE

    def test_error_messages_have_alert_icon(self):
        """Test that error messages have ALERT icon identifier."""
        assert "[ALERT]" in StreamMessages.ANALYSIS_FAILED
        assert "[ALERT]" in StreamMessages.INVALID_INPUT
        assert "[ALERT]" in StreamMessages.RATE_LIMIT_HIT

    def test_chart_icon_in_coverage_message(self):
        """Test that coverage calculation has CHART icon."""
        assert "[CHART]" in StreamMessages.CALCULATING_COVERAGE


class TestStatusMessages:
    """Tests for StatusMessages class."""

    def test_status_messages_exist(self):
        """Test that all status messages are defined."""
        assert StatusMessages.PROCESSING
        assert StatusMessages.VALIDATING
        assert StatusMessages.SAVING_RESULTS
        assert StatusMessages.READY
        assert StatusMessages.ERROR

    def test_status_messages_have_icons(self):
        """Test that status messages have appropriate icon identifiers."""
        assert "[INFO]" in StatusMessages.PROCESSING
        assert "[INFO]" in StatusMessages.VALIDATING
        assert "[INFO]" in StatusMessages.SAVING_RESULTS
        assert "[CHECK]" in StatusMessages.READY
        assert "[ALERT]" in StatusMessages.ERROR


class TestInfoMessages:
    """Tests for InfoMessages class."""

    def test_info_messages_exist(self):
        """Test that all info messages are defined."""
        assert InfoMessages.FIGMA_URL_TIP
        assert InfoMessages.PRD_TEXT_TIP
        assert InfoMessages.COMBINED_INPUT_TIP
        assert InfoMessages.STREAMING_MODE_TIP

    def test_info_messages_have_lightbulb_or_info_icon(self):
        """Test that info messages have LIGHTBULB or INFO icon identifiers."""
        # Tips use LIGHTBULB
        assert "[LIGHTBULB]" in InfoMessages.FIGMA_URL_TIP
        assert "[LIGHTBULB]" in InfoMessages.PRD_TEXT_TIP
        assert "[LIGHTBULB]" in InfoMessages.COMBINED_INPUT_TIP
        # Streaming mode tip uses INFO
        assert "[INFO]" in InfoMessages.STREAMING_MODE_TIP


class TestFormatProgressMessage:
    """Tests for format_progress_message function."""

    def test_basic_progress_message(self):
        """Test basic progress message formatting."""
        result = format_progress_message(5, 10)
        assert "[INFO]" in result
        assert "5/10" in result
        assert "50%" in result

    def test_progress_with_custom_item_type(self):
        """Test progress message with custom item type."""
        result = format_progress_message(3, 7, item_type="test cases")
        assert "[INFO]" in result
        assert "test cases" in result
        assert "3/7" in result
        assert "42%" in result

    def test_progress_at_start(self):
        """Test progress message at 0%."""
        result = format_progress_message(0, 100)
        assert "0/100" in result
        assert "0%" in result

    def test_progress_at_completion(self):
        """Test progress message at 100%."""
        result = format_progress_message(10, 10)
        assert "10/10" in result
        assert "100%" in result

    def test_progress_with_zero_total(self):
        """Test progress message handles zero total gracefully."""
        result = format_progress_message(0, 0)
        assert "0/0" in result
        assert "0%" in result

    def test_progress_percentage_calculation(self):
        """Test that percentage is calculated correctly."""
        result = format_progress_message(1, 3)
        assert "33%" in result  # 1/3 = 33.33% -> 33%

        result = format_progress_message(2, 3)
        assert "66%" in result  # 2/3 = 66.66% -> 66%


class TestFormatTestCaseMessage:
    """Tests for format_test_case_message function."""

    def test_basic_test_case_message(self):
        """Test basic test case message formatting."""
        result = format_test_case_message(1, "Login")
        assert "[CHECK]" in result
        assert "#1" in result
        assert "Login" in result

    def test_test_case_with_different_numbers(self):
        """Test test case messages with various case numbers."""
        result = format_test_case_message(42, "Authentication")
        assert "#42" in result
        assert "Authentication" in result

    def test_test_case_with_long_feature_name(self):
        """Test test case message with long feature name."""
        feature = "User Registration with Email Verification"
        result = format_test_case_message(5, feature)
        assert feature in result
        assert "#5" in result


class TestFormatCoverageMessage:
    """Tests for format_coverage_message function."""

    def test_coverage_message_with_integer(self):
        """Test coverage message with integer score."""
        result = format_coverage_message(85.0)
        assert "[CHART]" in result
        assert "85.0%" in result

    def test_coverage_message_with_decimal(self):
        """Test coverage message with decimal score."""
        result = format_coverage_message(72.5)
        assert "72.5%" in result

    def test_coverage_message_with_high_precision(self):
        """Test coverage message formats to 1 decimal place."""
        result = format_coverage_message(67.89123)
        assert "67.9%" in result

    def test_coverage_message_at_zero(self):
        """Test coverage message at 0%."""
        result = format_coverage_message(0.0)
        assert "0.0%" in result

    def test_coverage_message_at_hundred(self):
        """Test coverage message at 100%."""
        result = format_coverage_message(100.0)
        assert "100.0%" in result


class TestGetMessageWithData:
    """Tests for get_message_with_data function."""

    def test_message_only(self):
        """Test creating message dict with message only."""
        result = get_message_with_data("[INFO] Processing")
        assert result == {"message": "[INFO] Processing"}

    def test_message_with_single_data_field(self):
        """Test creating message dict with one data field."""
        result = get_message_with_data("[CHECK] Complete", count=5)
        assert result["message"] == "[CHECK] Complete"
        assert result["count"] == 5

    def test_message_with_multiple_data_fields(self):
        """Test creating message dict with multiple data fields."""
        result = get_message_with_data("[INFO] Analyzing", feature="Login", progress=50)
        assert result["message"] == "[INFO] Analyzing"
        assert result["feature"] == "Login"
        assert result["progress"] == 50

    def test_message_with_complex_data(self):
        """Test creating message dict with complex data structures."""
        test_cases = [{"id": 1, "name": "Test1"}, {"id": 2, "name": "Test2"}]
        result = get_message_with_data("[CHECK] Done", test_cases=test_cases, count=2)
        assert result["message"] == "[CHECK] Done"
        assert result["test_cases"] == test_cases
        assert result["count"] == 2

    def test_message_preserves_icon_identifiers(self):
        """Test that icon identifiers are preserved in message."""
        icons = ["[ROCKET]", "[CHECK]", "[ALERT]", "[INFO]", "[CHART]", "[LIGHTBULB]"]
        for icon in icons:
            result = get_message_with_data(f"{icon} Test message")
            assert icon in result["message"]

    def test_empty_kwargs(self):
        """Test that empty kwargs returns message-only dict."""
        result = get_message_with_data("[INFO] Test")
        assert len(result) == 1
        assert "message" in result
