"""Tests for framework.utils module."""

import logging
import os
from unittest.mock import patch


from framework.utils import (
    ensure_directories,
    format_file_size,
    load_environment,
    setup_logging,
    validate_api_keys,
)


class TestSetupLogging:
    """Tests for setup_logging function."""

    def test_setup_logging_default(self, caplog):
        """Test logging setup with default parameters."""
        with caplog.at_level(logging.INFO):
            setup_logging()
            logger = logging.getLogger(__name__)
            logger.info("Test message")
            assert "Test message" in caplog.text

    def test_setup_logging_with_file(self, tmp_path):
        """Test logging setup with file output."""
        log_file = tmp_path / "logs" / "test.log"
        setup_logging(log_file=log_file)

        # Verify file was created
        assert log_file.exists()

        # Verify directory was created
        assert log_file.parent.exists()

    def test_setup_logging_custom_level(self, caplog):
        """Test logging setup with custom level."""
        setup_logging(log_level="DEBUG")
        logger = logging.getLogger(__name__)

        with caplog.at_level(logging.DEBUG):
            logger.debug("Debug message")
            assert "Debug message" in caplog.text

    def test_setup_logging_custom_format(self, caplog):
        """Test logging setup with custom format."""
        custom_format = "%(levelname)s: %(message)s"
        setup_logging(format_string=custom_format)
        logger = logging.getLogger(__name__)

        with caplog.at_level(logging.INFO):
            logger.info("Formatted message")
            # caplog has its own format, just check message was logged
            assert "Formatted message" in caplog.text


class TestLoadEnvironment:
    """Tests for load_environment function."""

    def test_load_environment_existing_file(self, tmp_path, caplog):
        """Test loading environment from existing .env file."""
        env_file = tmp_path / ".env"
        env_file.write_text("TEST_VAR=test_value\n")

        with caplog.at_level(logging.INFO):
            load_environment(env_file)
            assert f"Loaded environment from: {env_file}" in caplog.text

        # Verify environment variable was loaded
        assert os.getenv("TEST_VAR") == "test_value"

        # Cleanup
        os.environ.pop("TEST_VAR", None)

    def test_load_environment_missing_file(self, tmp_path, caplog):
        """Test loading environment from non-existent .env file."""
        env_file = tmp_path / "nonexistent.env"

        with caplog.at_level(logging.WARNING):
            load_environment(env_file)
            assert f"Environment file not found: {env_file}" in caplog.text


class TestValidateApiKeys:
    """Tests for validate_api_keys function."""

    def test_validate_api_keys_all_present(self):
        """Test API key validation when all keys are present."""
        with patch.dict(
            os.environ,
            {
                "FIGMA_API_TOKEN": "test_figma",
                "ANTHROPIC_API_KEY": "test_anthropic",
                "OPENAI_API_KEY": "test_openai",
            },
        ):
            results = validate_api_keys()
            assert results == {
                "figma": True,
                "anthropic": True,
                "openai": True,
            }

    def test_validate_api_keys_partial(self):
        """Test API key validation when only some keys are present."""
        with patch.dict(
            os.environ,
            {
                "FIGMA_API_TOKEN": "test_figma",
            },
            clear=True,
        ):
            results = validate_api_keys()
            assert results == {
                "figma": True,
                "anthropic": False,
                "openai": False,
            }

    def test_validate_api_keys_none_present(self):
        """Test API key validation when no keys are present."""
        with patch.dict(os.environ, {}, clear=True):
            results = validate_api_keys()
            assert results == {
                "figma": False,
                "anthropic": False,
                "openai": False,
            }


class TestEnsureDirectories:
    """Tests for ensure_directories function."""

    def test_ensure_directories_creates_new(self, tmp_path):
        """Test creating new directories."""
        dirs = [
            tmp_path / "dir1",
            tmp_path / "dir2" / "subdir",
            tmp_path / "dir3" / "nested" / "deep",
        ]

        ensure_directories(dirs)

        # Verify all directories were created
        for d in dirs:
            assert d.exists()
            assert d.is_dir()

    def test_ensure_directories_existing(self, tmp_path):
        """Test ensuring existing directories don't cause errors."""
        dirs = [tmp_path / "existing"]
        dirs[0].mkdir(parents=True, exist_ok=True)

        # Should not raise any errors
        ensure_directories(dirs)
        assert dirs[0].exists()

    def test_ensure_directories_empty_list(self, tmp_path):
        """Test with empty directory list."""
        # Should not raise any errors
        ensure_directories([])


class TestFormatFileSize:
    """Tests for format_file_size function."""

    def test_format_bytes(self):
        """Test formatting bytes."""
        assert format_file_size(512) == "512.00 B"

    def test_format_kilobytes(self):
        """Test formatting kilobytes."""
        assert format_file_size(1024) == "1.00 KB"
        assert format_file_size(1536) == "1.50 KB"

    def test_format_megabytes(self):
        """Test formatting megabytes."""
        assert format_file_size(1024 * 1024) == "1.00 MB"
        assert format_file_size(1024 * 1024 * 2.5) == "2.50 MB"

    def test_format_gigabytes(self):
        """Test formatting gigabytes."""
        assert format_file_size(1024 * 1024 * 1024) == "1.00 GB"

    def test_format_terabytes(self):
        """Test formatting terabytes."""
        assert format_file_size(1024 * 1024 * 1024 * 1024) == "1.00 TB"

    def test_format_zero(self):
        """Test formatting zero bytes."""
        assert format_file_size(0) == "0.00 B"

    def test_format_decimal(self):
        """Test formatting decimal values."""
        assert format_file_size(1536.5) == "1.50 KB"
