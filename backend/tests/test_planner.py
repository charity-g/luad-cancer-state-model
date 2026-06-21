import pytest

from backend.agents.traverse_graph import cypher, planner


def test_fallback_gene_intervention_targets_gene():
    cy, params = planner._fallback("Will inhibiting KRAS help the LUAD cell state?")
    assert params["sym"] == "KRAS"
    assert "PERTURBS" in cy and "MUTATES" in cy
    assert cypher.is_read_only(cy)


def test_fallback_pathway_question_returns_results():
    # A pathway-name question yields a read-only fallback that returns a real
    # subgraph. (It may resolve via the gene branch when the pathway label
    # contains a gene symbol — either way it must produce results.)
    p = cypher.run_read(
        "MATCH (p:Pathway) WHERE p.id IS NOT NULL AND p.label IS NOT NULL "
        "RETURN p.label AS label LIMIT 1"
    )["rows"][0]
    cy, params = planner._fallback(f"Describe the {p['label']} pathway")
    assert cypher.is_read_only(cy)
    assert cypher.run_read(cy, params)["subgraph"]["nodes"]


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
