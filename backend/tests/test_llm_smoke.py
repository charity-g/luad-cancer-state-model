"""LLM smoke tests — only run when ANTHROPIC_API_KEY is set.

These exercise the *real* text2Cypher and reasoner paths: Claude generates Cypher
from NEO4J_SCHEMA.md, it must be read-only and actually execute, and the reasoner
must return a usable report/verdict.
"""

import os

import pytest

from backend.agent import agent, cypher, planner

pytestmark = pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="requires ANTHROPIC_API_KEY for the live LLM path",
)


def test_planner_generates_executable_readonly_cypher():
    plan = planner.plan("Which essential genes belong to activated pathways?")
    assert plan["source"] == "llm"
    assert cypher.is_read_only(plan["cypher"])
    result = cypher.run_read(plan["cypher"], plan["params"])  # generated Cypher runs
    assert "rows" in result


def test_agent_llm_intervention_report():
    r = agent.run("Will inhibiting KRAS help the LUAD cell state?")
    assert r["verdict"] in ("beneficial", "harmful", "negligible", "uncertain")
    assert len(r["report"]) > 50
    # KRAS is a known driver — the answer must be grounded in a real subgraph,
    # not an empty result.
    assert r["subgraph"]["nodes"], "expected a non-empty subgraph for a KRAS query"


def test_agent_llm_describe_report():
    r = agent.run("What is the state of the MAPK signaling pathway in LUAD?")
    assert r["report"]
    assert cypher.is_read_only(r["cypher"])
