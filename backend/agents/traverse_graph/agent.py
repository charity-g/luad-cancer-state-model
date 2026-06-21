"""Agent orchestration — the single seam the backend wraps.

run(question, mutations, context, history) -> {
    question, cypher, plan_source, report, verdict, subgraph, rows, cited_pathways
}

Flow:  plan (text2Cypher)  ->  execute (read-only)  ->  reason
The uploaded sample profile (mutations/context) and recent chat history are
woven into the planner and reasoner so answers are grounded in the profile and
follow-ups build on prior turns. If the generated Cypher errors or returns
nothing, fall back to a deterministic query.
"""

from neo4j.exceptions import Neo4jError

from backend.agents import drug_routing
from backend.agents.traverse_graph import cypher, planner, reasoner


def _profile_text(mutations, context):
    # The user's current selection (context) is the PRIMARY subject; the uploaded
    # sample mutations are only background. Otherwise a vague question ("can I
    # inhibit this?") latches onto the profile (e.g. KRAS) instead of the
    # selected node (e.g. mTOR).
    parts = []
    proteins = [c["protein"] for c in (context or []) if c.get("protein")]
    if proteins:
        parts.append(
            f"PRIMARY SUBJECT: {', '.join(proteins)} (the user's current selection). "
            f"Interpret 'this'/'it' as {proteins[0]} unless the question names "
            f"something else. Answer about the PRIMARY SUBJECT."
        )
    muts = []
    for m in mutations or []:
        name = m.get("protein") or m.get("mutation_id") or "?"
        eff = m.get("estimated_effect") or m.get("effect") or "?"
        muts.append(f"{name} ({eff})")
    if muts:
        parts.append(
            "Background sample mutations (context only, not the subject unless asked): "
            + "; ".join(muts)
        )
    return "\n".join(parts)


def _history_text(history):
    lines = []
    for turn in (history or [])[-6:]:  # last few turns is enough context
        role = turn.get("role", "?")
        content = (turn.get("content") or "").strip()[:500]
        if content:
            lines.append(f"{role}: {content}")
    return "\n".join(lines)


def _enrich_edges(subgraph):
    """Add every relationship that exists among the subgraph's nodes."""
    ids = [n["id"] for n in subgraph["nodes"] if n.get("id")]  # ids are elementIds
    if len(ids) < 2:
        return subgraph
    extra = cypher.run_read(
        "MATCH (a)-[r]->(b) WHERE elementId(a) IN $ids AND elementId(b) IN $ids "
        "RETURN a, r, b",
        {"ids": ids},
    )["subgraph"]
    nodes_by = {n["id"]: n for n in subgraph["nodes"]}
    for n in extra["nodes"]:
        nodes_by.setdefault(n["id"], n)
    seen = {(e["source"], e["target"], e["type"]) for e in subgraph["edges"]}
    edges = list(subgraph["edges"])
    for e in extra["edges"]:
        key = (e["source"], e["target"], e["type"])
        if key not in seen:
            seen.add(key)
            edges.append(e)
    return {"nodes": list(nodes_by.values()), "edges": edges}


def run(question, mutations=None, context=None, history=None):
    profile = _profile_text(mutations, context)
    convo = _history_text(history)

    plan = planner.plan(question, profile=profile, history=convo)
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

    # Connect the dots: pull every relationship that exists among the retrieved
    # nodes, so the visualized subgraph is fully wired, not just the edges the
    # query happened to return.
    result["subgraph"] = _enrich_edges(result["subgraph"])

    # Drug-routing evidence (graph lookup + ML fallback) for the uploaded
    # profile. Best-effort: a failure here must never break the chat answer.
    try:
        routing = drug_routing.route(mutations)
        evidence = drug_routing.evidence_text(mutations)
    except Exception:
        routing, evidence = [], ""

    report = reasoner.reason(question, result, profile=profile, history=convo, evidence=evidence)
    pathway_ids = [
        n.get("key") or n.get("label") or n["id"]
        for n in result["subgraph"]["nodes"]
        if "Pathway" in n.get("labels", [])
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
        "drug_routing": routing,
    }
