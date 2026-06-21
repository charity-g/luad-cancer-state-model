from backend.agnets.traverse_graphimport agent, cypher
from backend.agent.reasoner import VERDICTS

EXPECTED_KEYS = {
    "question", "cypher", "plan_source", "report",
    "verdict", "subgraph", "rows", "cited_pathways",
}


def test_run_returns_full_contract(force_fallback):
    r = agent.run("Describe the MAPK signaling pathway")
    assert EXPECTED_KEYS <= set(r)
    assert cypher.is_read_only(r["cypher"])
    assert r["report"]


def test_intervention_question_yields_verdict(force_fallback):
    r = agent.run("Will inhibiting KRAS help the LUAD cell state?")
    assert r["verdict"] in VERDICTS
    labels = {l for n in r["subgraph"]["nodes"] for l in n["labels"]}
    assert {"Gene", "Pathway"} <= labels


def test_describe_question_has_no_verdict(force_fallback):
    r = agent.run("Describe the MAPK signaling pathway")
    assert r["verdict"] is None
    assert r["cited_pathways"]


def test_cited_pathways_are_pathway_nodes(force_fallback):
    r = agent.run("Describe the MAPK signaling pathway")
    pathway_ids = {n["id"] for n in r["subgraph"]["nodes"] if "Pathway" in n["labels"]}
    assert set(r["cited_pathways"]) == pathway_ids
