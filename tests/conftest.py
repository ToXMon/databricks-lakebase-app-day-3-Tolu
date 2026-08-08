"""
Shared pytest fixtures for the weather MCP server test suite.

All HTTP is mocked - no live network calls, no Databricks auth. We swap
`openmeteo_adapter._session` with a `FakeSession` per-test rather than
monkeypatching global `requests`, so tests stay isolated from each other
and from any real HTTP client state.
"""

import sys
from pathlib import Path

import pytest

# Make `mcp_server` importable as a package when running pytest from day3/.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mcp_server import openmeteo_adapter  # noqa: E402


class FakeResponse:
    """Minimal stand-in for requests.Response used by FakeSession."""

    def __init__(self, json_data=None, status_code=200, text="", raise_json_error=False):
        self._json_data = json_data
        self.status_code = status_code
        self.text = text
        self._raise_json_error = raise_json_error

    def json(self):
        if self._raise_json_error:
            raise ValueError("Invalid JSON")
        return self._json_data


class FakeSession:
    """
    Drop-in replacement for requests.Session.get() driven by a queue of
    canned responses (or a single response reused for every call), or a
    callable for dynamic behavior.
    """

    def __init__(self, response=None, responses=None, side_effect=None):
        self._response = response
        self._responses = list(responses) if responses is not None else None
        self._side_effect = side_effect
        self.calls = []

    def get(self, url, params=None, timeout=None):
        self.calls.append({"url": url, "params": params, "timeout": timeout})
        if self._side_effect is not None:
            return self._side_effect(url, params, timeout)
        if self._responses is not None:
            return self._responses.pop(0)
        return self._response


@pytest.fixture
def fake_session_factory():
    """Return the FakeSession/FakeResponse classes for tests to build with."""
    return FakeSession, FakeResponse


@pytest.fixture(autouse=True)
def _restore_adapter_session():
    """Ensure each test starts/ends with a clean adapter session slot."""
    original_session = openmeteo_adapter._session
    yield
    openmeteo_adapter._session = original_session
