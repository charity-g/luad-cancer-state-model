"""Agent orchestration — the single seam the backend wraps.

run(question) -> {
    question, cypher, plan_source, report, verdict, subgraph, rows, cited_pathways
}

Flow:  plan (text2Cypher)  ->  execute (read-only)  ->  reason
If the generated Cypher errors, fall back to a deterministic query and retry once.
"""

from neo4j.exceptions import Neo4jError

from backend.agents.traverse_graph import cypher, planner, reasoner


def run(question):
    plan = planner.plan(question)
    try:
        result = cypher.run_read(plan["cypher"], plan["params"])
    except (Neo4jError, ValueError):
        result = None  # invalid or non-read-only Cypher

    # Fall back deterministically if the generated query errored or returned
    # nothing usable — better a relevant subgraph than an empty answer.
    if result is None or (not result["subgraph"]["nodes"] and not result["rows"]):
        cy, params = planner._fallback(question)
        plan = {"cypher": cy, "params": params, "source": "fallback"}
        result = cypher.run_read(cy, params)

    report = reasoner.reason(question, result)
    pathway_ids = [
        n["id"] for n in result["subgraph"]["nodes"] if "Pathway" in n.get("labels", [])
    ]
    return {
        "question": question,
        "cypher": plan["cypher"],
        "plan_source": plan["source"],
        "report": report["report"],
        "verdict": report.get("verdict"),
        "subgraph": result["subgraph"],
        "rows": result["rows"],
        "cited_pathways": pathway_ids,
    }
