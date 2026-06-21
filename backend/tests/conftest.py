"""Shared fixtures.

Tests run against whatever DB ``backend/.env`` points at — normally the shared
Aura cloud graph over the HTTP Query API (port 443). They are **read-only**: the
suite never wipes or mutates the shared graph (the read-only guard enforces this).

`graph_available` skips the whole suite cleanly if the DB is unreachable or empty
(e.g. no `.env`, or the graph hasn't been loaded yet via
`scripts/init_neo4j/upload_http.py`). `force_fallback` disables the LLM path so
the core suite is deterministic and free even when ANTHROPIC_API_KEY is set.
"""

import pytest

from backend.agents.traverse_graph import cypher


@pytest.fixture(scope="session", autouse=True)
def graph_available():
    try:
        count = cypher.run_read("MATCH (n) RETURN count(n) AS c")["rows"][0]["c"]
    except Exception as e:  # unreachable / bad creds
        pytest.skip(f"graph DB not reachable — check backend/.env ({e})")
    if not count:
        pytest.skip("graph DB is empty — load it first (scripts/init_neo4j/upload_http.py)")
    yield


@pytest.fixture
def force_fallback(monkeypatch):
    monkeypatch.setattr("backend.agents.traverse_graph.planner.ANTHROPIC_API_KEY", None)
    monkeypatch.setattr("backend.agents.traverse_graph.reasoner.ANTHROPIC_API_KEY", None)
