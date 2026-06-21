import pytest

from backend.agnets.traverse_graphimport cypher, planner


def test_fallback_gene_intervention_targets_gene():
    cy, params = planner._fallback("Will inhibiting KRAS help the LUAD cell state?")
    assert params["sym"] == "KRAS"
    assert "PERTURBS" in cy and "MUTATES" in cy
    assert cypher.is_read_only(cy)


def test_fallback_pathway_targets_pathway():
    cy, params = planner._fallback("Describe the MAPK signaling pathway")
    assert params.get("pid") == "MAPK_signaling"
    assert cypher.is_read_only(cy)


def test_fallback_no_entity_returns_overview():
    cy, params = planner._fallback("tell me something interesting")
    assert "activated" in cy
    assert cypher.is_read_only(cy)


@pytest.mark.parametrize("question", [
    "Will inhibiting EGFR help?",
    "Describe the MAPK signaling pathway",
    "what mutations matter",
    "completely unrelated text",
])
def test_every_fallback_query_executes(question):
    cy, params = planner._fallback(question)
    result = cypher.run_read(cy, params)  # must not raise
    assert "subgraph" in result and "rows" in result


def test_plan_always_returns_readonly_cypher(force_fallback):
    for q in ["inhibit KRAS", "MAPK signaling pathway", "anything"]:
        plan = planner.plan(q)
        assert plan["source"] == "fallback"
        assert cypher.is_read_only(plan["cypher"])
