"""Shared fixtures.

The graph is (re)loaded once per session so tests run against a known state
(157 nodes / 298 edges). `force_fallback` disables the LLM path so the core
suite is deterministic and free even when ANTHROPIC_API_KEY is set.
"""

import pytest

from backend import dev_load_graph


@pytest.fixture(scope="session", autouse=True)
def graph_loaded():
    dev_load_graph.main()
    yield


@pytest.fixture
def force_fallback(monkeypatch):
    monkeypatch.setattr("backend.agent.planner.ANTHROPIC_API_KEY", None)
    monkeypatch.setattr("backend.agent.reasoner.ANTHROPIC_API_KEY", None)
