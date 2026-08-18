"""Utility functions for the test generator framework."""

import logging
import os
import sys
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv


def setup_logging(
    log_level: Optional[str] = None,
    log_file: Optional[Path] = None,
    format_string: Optional[str] = None,
) -> None:
    """Setup logging configuration.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
                   Defaults to LOG_LEVEL env var or INFO.
        log_file: Optional path to log file. Defaults to LOG_FILE env var if set.
        format_string: Optional custom format string.
    """
    # Load from environment variables with fallbacks
    log_level = log_level or os.getenv("LOG_LEVEL", "INFO")
    log_file = log_file or (
        Path(os.getenv("LOG_FILE")) if os.getenv("LOG_FILE") else None
    )

    if format_string is None:
        log_format = os.getenv("LOG_FORMAT", "text")
        if log_format == "json":
            format_string = '{"timestamp":"%(asctime)s","name":"%(name)s","level":"%(levelname)s","message":"%(message)s"}'
        else:
            format_string = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    handlers = [logging.StreamHandler(sys.stdout)]

    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_file))

    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format=format_string,
        handlers=handlers,
    )

    logger = logging.getLogger(__name__)
    logger.info(
        f"Logging initialized at {log_level} level (format: {log_format if format_string is None else 'custom'})"
    )


def load_environment(env_file: Path = Path(".env")) -> None:
    """Load environment variables from .env file.

    Args:
        env_file: Path to .env file.
    """
    if env_file.exists():
        load_dotenv(env_file)
        logger = logging.getLogger(__name__)
        logger.info(f"Loaded environment from: {env_file}")
    else:
        logger = logging.getLogger(__name__)
        logger.warning(f"Environment file not found: {env_file}")


def validate_api_keys() -> dict[str, bool]:
    """Validate that required API keys are configured.

    Returns:
        Dictionary with validation results for each key.
    """
    import os

    results = {
        "figma": bool(os.getenv("FIGMA_API_TOKEN")),
        "anthropic": bool(os.getenv("ANTHROPIC_API_KEY")),
        "openai": bool(os.getenv("OPENAI_API_KEY")),
    }

    logger = logging.getLogger(__name__)
    logger.info(f"API key validation: {results}")

    return results


def ensure_directories(directories: list[Path]) -> None:
    """Ensure required directories exist.

    Args:
        directories: List of directory paths to create.
    """
    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(__name__)
    logger.info(f"Ensured {len(directories)} directories exist")


def format_file_size(size_bytes: float) -> str:
    """Format file size in human-readable format.

    Args:
        size_bytes: Size in bytes.

    Returns:
        Formatted string (e.g., "1.5 MB").
    """
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} TB"
