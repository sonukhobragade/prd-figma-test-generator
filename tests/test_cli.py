"""Tests for CLI interface (cli.py)."""

import os
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from click.testing import CliRunner

from framework.models import PRDDocument, TestChecklist, TestPoint

# Mock environment before importing cli
with patch.dict(
    "os.environ",
    {
        "ANTHROPIC_API_KEY": "test_key",
        "FIGMA_API_TOKEN": "test_figma_token",
    },
):
    from cli import cli


@pytest.fixture
def runner():
    """Create Click test runner."""
    return CliRunner()


@pytest.fixture
def sample_checklist_file(tmp_path):
    """Create sample checklist markdown file."""
    checklist_content = """# Test Checklist: Login Feature

## Test Points

### P0 - Critical
- [ ] TP001: User can login with valid credentials (Login) [positive]

### P1 - High Priority
- [ ] TP002: Invalid credentials show error (Login) [negative]

## Coverage Score: 85.0%
"""
    checklist_path = tmp_path / "checklist.md"
    checklist_path.write_text(checklist_content)
    return checklist_path


@pytest.fixture
def sample_prd_file(tmp_path):
    """Create sample PRD file."""
    prd_path = tmp_path / "test_prd.pdf"
    # Create minimal PDF-like content
    prd_path.write_bytes(b"%PDF-1.4\nTest PRD content")
    return prd_path


class TestCLIGroup:
    """Tests for main CLI group."""

    def test_cli_help(self, runner):
        """Test CLI help message."""
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0, result.output
        assert "PRD-to-Figma Test Case Generator CLI" in result.output

    def test_cli_version_option(self, runner):
        """Test CLI accepts log-level option."""
        result = runner.invoke(cli, ["--log-level", "DEBUG", "--help"])
        assert result.exit_code == 0, result.output

    def test_cli_with_env_file(self, runner, tmp_path):
        """Test CLI accepts env-file option."""
        env_file = tmp_path / ".env.test"
        env_file.write_text("ANTHROPIC_API_KEY=test_key\n")
        result = runner.invoke(cli, ["--env-file", str(env_file), "--help"])
        assert result.exit_code == 0, result.output

    def test_cli_creates_log_directory(self, runner, tmp_path):
        """Test CLI creates logs directory."""
        with runner.isolated_filesystem(temp_dir=tmp_path):
            # --help is handled eagerly by click and returns before the group
            # callback runs, so it never reaches the log-directory setup.
            runner.invoke(cli, ["analyze", "--prd", "missing.pdf"])
            # Log directory should be created
            assert Path("logs").exists()


class TestAnalyzeCommand:
    """Tests for analyze command."""

    @patch("cli.LLMAnalyzer")
    @patch("cli.PRDUploader")
    def test_analyze_success(
        self,
        mock_uploader_class,
        mock_analyzer_class,
        runner,
        sample_prd_file,
        tmp_path,
    ):
        """Test successful PRD analysis via CLI."""
        # Setup mocks
        mock_uploader = Mock()
        mock_uploader_class.return_value = mock_uploader

        mock_prd = PRDDocument(
            file_path=sample_prd_file,
            file_type="pdf",
            file_size_mb=1.5,
            content="Test PRD content",
            images=[],
        )
        mock_uploader.upload.return_value = mock_prd

        mock_analyzer = Mock()
        mock_analyzer_class.return_value = mock_analyzer

        mock_checklist = TestChecklist(
            feature_name="Login",
            test_points=[
                TestPoint(
                    id="TP001",
                    description="User can login",
                    feature="Login",
                    priority="P0",
                    test_type="positive",
                )
            ],
            coverage_score=85.0,
        )
        mock_analyzer.analyze_prd.return_value = mock_checklist
        mock_analyzer.generate_checklist_markdown.return_value = "# Checklist"

        output_path = tmp_path / "output" / "checklist.md"

        result = runner.invoke(
            cli,
            [
                "analyze",
                "--prd",
                str(sample_prd_file),
                "--output",
                str(output_path),
                "--feature-name",
                "Login",
            ],
        )

        assert result.exit_code == 0, result.output
        assert "Analyzing PRD" in result.output
        assert "Generated 1 test points" in result.output
        assert "Coverage: 85.0%" in result.output
        assert output_path.exists()

    def test_analyze_missing_prd(self, runner):
        """Test analyze command with missing PRD file."""
        result = runner.invoke(
            cli, ["analyze", "--prd", "/nonexistent/file.pdf", "--output", "output.md"]
        )
        assert result.exit_code != 0

    def test_analyze_missing_api_key(self, runner, sample_prd_file, tmp_path):
        """Test analyze command without API key."""
        with patch.dict(os.environ, {}, clear=True):
            with patch("cli.PRDUploader") as mock_uploader_class:
                mock_uploader = Mock()
                mock_uploader_class.return_value = mock_uploader
                mock_prd = PRDDocument(
                    file_path=sample_prd_file,
                    file_type="pdf",
                    file_size_mb=1.0,
                    content="Test",
                )
                mock_uploader.upload.return_value = mock_prd

                result = runner.invoke(
                    cli,
                    [
                        "analyze",
                        "--prd",
                        str(sample_prd_file),
                        "--output",
                        str(tmp_path / "out.md"),
                    ],
                )
                assert result.exit_code == 1
                assert "ANTHROPIC_API_KEY not found" in result.output

    @patch("cli.LLMAnalyzer")
    @patch("cli.PRDUploader")
    def test_analyze_with_exception(
        self,
        mock_uploader_class,
        mock_analyzer_class,
        runner,
        sample_prd_file,
        tmp_path,
    ):
        """Test analyze command handles exceptions gracefully."""
        mock_uploader = Mock()
        mock_uploader_class.return_value = mock_uploader
        mock_uploader.upload.side_effect = Exception("Upload failed")

        result = runner.invoke(
            cli,
            [
                "analyze",
                "--prd",
                str(sample_prd_file),
                "--output",
                str(tmp_path / "out.md"),
            ],
        )
        assert result.exit_code == 1
        assert "Error:" in result.output


class TestFigmaCommand:
    """Tests for figma command."""

    @patch("cli.LLMAnalyzer")
    @patch("cli.FigmaClient")
    def test_figma_success(
        self, mock_figma_class, mock_analyzer_class, runner, tmp_path
    ):
        """Test successful Figma analysis via CLI."""
        # Setup mocks
        mock_figma = Mock()
        mock_figma_class.return_value = mock_figma

        # cli.py calls import_from_url and reads design.name; fetch_design
        # no longer exists.
        mock_design = Mock()
        mock_design.name = "Login Screen"
        mock_figma.import_from_url.return_value = mock_design

        mock_analyzer = Mock()
        mock_analyzer_class.return_value = mock_analyzer

        mock_checklist = TestChecklist(
            feature_name="Login UI",
            test_points=[
                TestPoint(
                    id="TP001",
                    description="UI elements visible",
                    feature="Login",
                    priority="P0",
                    test_type="positive",
                )
            ],
            coverage_score=90.0,
        )
        # cli.py routes Figma designs through analyze_prd, and takes
        # len(checklist.test_points), so this must be a real TestChecklist.
        mock_analyzer.analyze_prd.return_value = mock_checklist
        mock_analyzer.generate_checklist_markdown.return_value = "# Figma Checklist"

        output_path = tmp_path / "figma_checklist.md"

        result = runner.invoke(
            cli,
            [
                "figma",
                "--url",
                "https://figma.com/file/abc123?node-id=1-2",
                "--output",
                str(output_path),
            ],
        )

        assert result.exit_code == 0, result.output
        assert "Importing from Figma" in result.output
        assert "Generated 1 test points" in result.output
        assert output_path.exists()

    def test_figma_missing_url(self, runner, tmp_path):
        """Test figma command without URL."""
        result = runner.invoke(cli, ["figma", "--output", str(tmp_path / "out.md")])
        assert result.exit_code != 0

    @patch("cli.FigmaClient")
    def test_figma_with_exception(self, mock_figma_class, runner, tmp_path):
        """Test figma command handles exceptions."""
        mock_figma = Mock()
        mock_figma_class.return_value = mock_figma
        mock_figma.fetch_design.side_effect = Exception("API error")

        result = runner.invoke(
            cli,
            [
                "figma",
                "--url",
                "https://figma.com/file/test",
                "--output",
                str(tmp_path / "out.md"),
            ],
        )
        assert result.exit_code == 1
        assert "Error:" in result.output


class TestExpandCommand:
    """Tests for expand command."""

    @patch("cli.TestCaseExpander")
    def test_expand_success(
        self, mock_expander_class, runner, sample_checklist_file, tmp_path
    ):
        """Test successful test case expansion."""
        mock_expander = Mock()
        mock_expander_class.return_value = mock_expander

        # Mock the expansion process
        from framework.models import TestCase

        mock_test_cases = [
            TestCase(
                test_case_id="TC001_P0_Login",
                priority="P0",
                category="Functional",
                screen_reference="Login",
                precondition="App is open",
                test_scenario="User can login",
                steps_to_execute="1. Navigate to login\n2. Enter credentials",
                expected_result="Login succeeds",
                feature="Login",
                comments="Critical test",
            )
        ]
        mock_expander.expand_checklist.return_value = mock_test_cases
        # cli.py indexes into the summary, so a bare Mock is not subscriptable.
        mock_expander.generate_summary_report.return_value = {
            "total_cases": len(mock_test_cases),
            "by_priority": {"P0": len(mock_test_cases)},
        }

        testcases_path = tmp_path / "testcases.csv"

        # This command needs to parse the checklist markdown
        # For now, we'll test that it fails gracefully with our simple mock
        result = runner.invoke(
            cli,
            [
                "expand",
                "--checklist",
                str(sample_checklist_file),
                "--testcases",
                str(testcases_path),
            ],
        )

        # The command should run, though it may fail parsing our simple checklist
        # At minimum it should not crash
        # The expand command is a stub: it prints a note pointing at the
        # generate command and exits 0 without doing any work.
        assert "generate" in result.output

    def test_expand_missing_checklist(self, runner, tmp_path):
        """Test expand command with missing checklist."""
        result = runner.invoke(
            cli,
            [
                "expand",
                "--checklist",
                "/nonexistent/checklist.md",
                "--testcases",
                str(tmp_path / "out.csv"),
            ],
        )
        assert result.exit_code != 0


class TestGenerateCommand:
    """Tests for generate command (full pipeline)."""

    @patch("cli.TestCaseExpander")
    @patch("cli.LLMAnalyzer")
    @patch("cli.PRDUploader")
    def test_generate_success(
        self,
        mock_uploader_class,
        mock_analyzer_class,
        mock_expander_class,
        runner,
        sample_prd_file,
        tmp_path,
    ):
        """Test successful full pipeline generation."""
        # Setup mocks
        mock_uploader = Mock()
        mock_uploader_class.return_value = mock_uploader
        mock_prd = PRDDocument(
            file_path=sample_prd_file,
            file_type="pdf",
            file_size_mb=1.0,
            content="Test content",
        )
        mock_uploader.upload.return_value = mock_prd

        mock_analyzer = Mock()
        mock_analyzer_class.return_value = mock_analyzer
        mock_checklist = TestChecklist(
            feature_name="Feature",
            test_points=[
                TestPoint(
                    id="TP001",
                    description="Test",
                    feature="Feature",
                    priority="P0",
                    test_type="positive",
                )
            ],
            coverage_score=80.0,
        )
        mock_analyzer.analyze_prd.return_value = mock_checklist
        mock_analyzer.generate_checklist_markdown.return_value = "# Checklist"

        mock_expander = Mock()
        mock_expander_class.return_value = mock_expander
        from framework.models import TestCase

        mock_test_cases = [
            TestCase(
                test_case_id="TC001",
                priority="P0",
                category="Functional",
                screen_reference="Feature",
                precondition="App is open",
                test_scenario="Test",
                steps_to_execute="Steps",
                expected_result="Result",
                feature="Feature",
                comments="",
            )
        ]
        mock_expander.expand_checklist.return_value = mock_test_cases
        # cli.py indexes into the summary, so a bare Mock is not subscriptable.
        mock_expander.generate_summary_report.return_value = {
            "total_cases": len(mock_test_cases),
            "by_priority": {"P0": len(mock_test_cases)},
        }

        checklist_path = tmp_path / "checklist.md"
        testcases_path = tmp_path / "testcases.csv"

        result = runner.invoke(
            cli,
            [
                "generate",
                "--prd",
                str(sample_prd_file),
                "--checklist",
                str(checklist_path),
                "--testcases",
                str(testcases_path),
                "--feature-name",
                "Feature",
            ],
        )

        assert result.exit_code == 0, result.output
        assert "Workflow complete!" in result.output
        assert checklist_path.exists()
        # export_to_csv is mocked, so no file is written; assert the CLI
        # asked for it at the right path instead.
        mock_expander.export_to_csv.assert_called_once()
        assert str(testcases_path) in str(mock_expander.export_to_csv.call_args)

    def test_generate_missing_prd(self, runner, tmp_path):
        """Test generate command with missing PRD."""
        result = runner.invoke(
            cli,
            [
                "generate",
                "--prd",
                "/nonexistent/file.pdf",
                "--checklist",
                str(tmp_path / "check.md"),
                "--testcases",
                str(tmp_path / "test.csv"),
            ],
        )
        assert result.exit_code != 0


class TestBatchCommand:
    """Tests for batch command."""

    @patch("cli.LLMAnalyzer")
    @patch("cli.PRDUploader")
    def test_batch_success(
        self, mock_uploader_class, mock_analyzer_class, runner, tmp_path
    ):
        """Test successful batch processing."""
        # Create input directory with PRD files
        input_dir = tmp_path / "input"
        input_dir.mkdir()
        (input_dir / "prd1.pdf").write_bytes(b"%PDF-1.4\nTest1")
        (input_dir / "prd2.pdf").write_bytes(b"%PDF-1.4\nTest2")

        output_dir = tmp_path / "output"

        # Setup mocks
        mock_uploader = Mock()
        mock_uploader_class.return_value = mock_uploader
        mock_prd = PRDDocument(
            file_path=Path("test.pdf"),
            file_type="pdf",
            file_size_mb=1.0,
            content="Test",
        )
        mock_uploader.upload.return_value = mock_prd

        mock_analyzer = Mock()
        mock_analyzer_class.return_value = mock_analyzer
        mock_checklist = TestChecklist(
            feature_name="Feature",
            test_points=[
                TestPoint(
                    id="TP001",
                    description="Test",
                    feature="Feature",
                    priority="P0",
                    test_type="positive",
                )
            ],
            coverage_score=75.0,
        )
        mock_analyzer.analyze_prd.return_value = mock_checklist
        mock_analyzer.generate_checklist_markdown.return_value = "# Checklist"

        result = runner.invoke(
            cli,
            ["batch", "--input-dir", str(input_dir), "--output-dir", str(output_dir)],
        )

        assert result.exit_code == 0, result.output
        assert "Batch processing 2 files" in result.output
        assert "Batch processing complete!" in result.output

    def test_batch_empty_directory(self, runner, tmp_path):
        """Test batch with empty input directory."""
        input_dir = tmp_path / "input"
        input_dir.mkdir()
        output_dir = tmp_path / "output"

        result = runner.invoke(
            cli,
            ["batch", "--input-dir", str(input_dir), "--output-dir", str(output_dir)],
        )

        # An empty input directory is treated as a failure: a batch run that
        # processed nothing should not report success to a caller.
        assert result.exit_code != 0
        assert "No PRD files found" in result.output

    def test_batch_missing_directory(self, runner, tmp_path):
        """Test batch with nonexistent input directory."""
        result = runner.invoke(
            cli,
            [
                "batch",
                "--input-dir",
                "/nonexistent/dir",
                "--output-dir",
                str(tmp_path / "out"),
            ],
        )
        assert result.exit_code != 0


class TestCLIOptions:
    """Tests for CLI options and flags."""

    def test_log_level_debug(self, runner):
        """Test CLI with DEBUG log level."""
        result = runner.invoke(cli, ["--log-level", "DEBUG", "--help"])
        assert result.exit_code == 0, result.output

    def test_log_level_warning(self, runner):
        """Test CLI with WARNING log level."""
        result = runner.invoke(cli, ["--log-level", "WARNING", "--help"])
        assert result.exit_code == 0, result.output

    def test_log_level_error(self, runner):
        """Test CLI with ERROR log level."""
        result = runner.invoke(cli, ["--log-level", "ERROR", "--help"])
        assert result.exit_code == 0, result.output

    def test_invalid_log_level(self, runner):
        """Test CLI with invalid log level."""
        # Same reason: --help short-circuits before validation, so pair the
        # bad value with a real subcommand.
        result = runner.invoke(cli, ["--log-level", "INVALID", "analyze", "--prd", "x.pdf"])
        assert result.exit_code != 0
        assert "INVALID" in result.output


class TestCLIErrorHandling:
    """Tests for CLI error handling."""

    def test_keyboard_interrupt_handling(self, runner, sample_prd_file):
        """Test CLI handles keyboard interrupt gracefully."""
        with patch("cli.PRDUploader") as mock_uploader_class:
            mock_uploader = Mock()
            mock_uploader_class.return_value = mock_uploader
            mock_uploader.upload.side_effect = KeyboardInterrupt()

            result = runner.invoke(
                cli, ["analyze", "--prd", str(sample_prd_file), "--output", "out.md"]
            )
            # Should exit with error
            assert result.exit_code != 0

    def test_general_exception_handling(self, runner, sample_prd_file):
        """Test CLI handles general exceptions."""
        with patch("cli.PRDUploader") as mock_uploader_class:
            mock_uploader = Mock()
            mock_uploader_class.return_value = mock_uploader
            mock_uploader.upload.side_effect = RuntimeError("Unexpected error")

            result = runner.invoke(
                cli, ["analyze", "--prd", str(sample_prd_file), "--output", "out.md"]
            )
            assert result.exit_code == 1
            assert "Error:" in result.output
