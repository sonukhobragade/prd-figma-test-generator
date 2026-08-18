"""
Shared fixtures.

`make_test_case` exists because TestCase gained four required fields
(category, screen_reference, precondition, test_scenario) and renamed two
others: requirement_description became test_scenario, and test_step became
steps_to_execute. Every test that built one by hand broke, and each was
repeating the same eight-field literal. Building them through one factory
means the next schema change is a single edit rather than another sweep.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from framework.models import TestCase  # noqa: E402  (needs the path insert above)


def build_test_case(**overrides) -> TestCase:
    """A valid TestCase; pass keyword arguments to vary any field."""
    fields = {
        "test_case_id": "TC001",
        "priority": "P0",
        "category": "Functional",
        "screen_reference": "Login",
        "precondition": "User is on the login screen",
        "test_scenario": "User logs in with valid credentials",
        "steps_to_execute": "[check1] Enter credentials\n[check2] Submit",
        "expected_result": "Success",
        "feature": "Login",
    }
    fields.update(overrides)
    return TestCase(**fields)


@pytest.fixture
def make_test_case():
    """Factory fixture wrapping :func:`build_test_case`."""
    return build_test_case


@pytest.fixture
def test_case(make_test_case) -> TestCase:
    """A single ready-made TestCase for tests that only need one."""
    return make_test_case()


@pytest.fixture(autouse=True)
def _api_keys(monkeypatch):
    """Give the CLI an API key.

    cli.py checks ANTHROPIC_API_KEY in the environment before it constructs
    the analyzer, so mocking LLMAnalyzer is not enough: the command exits 1
    first. Tests that assert the missing-key path clear the environment
    themselves, so this does not mask them.
    """
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-not-real")
    monkeypatch.setenv("FIGMA_API_TOKEN", "test-token-not-real")
