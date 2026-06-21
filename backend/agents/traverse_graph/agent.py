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

from backend.agents.traverse_graph import cypher, planner, reasoner


def _profile_text(mutations, context):
    parts = []
    for m in mutations or []:
        name = m.get("protein") or m.get("mutation_id") or "?"
        eff = m.get("estimated_effect") or m.get("effect") or "?"
        parts.append(f"{name} ({eff})")
    for c in context or []:
        if c.get("protein"):
            parts.append(f"{c['protein']} ({c.get('effect', '?')})")
    return "Sample mutation profile: " + "; ".join(parts) if parts else ""


def _history_text(history):
    lines = []
    for turn in (history or [])[-6:]:  # last few turns is enough context
        role = turn.get("role", "?")
        content = (turn.get("content") or "").strip()[:500]
        if content:
            lines.append(f"{role}: {content}")
    return "\n".join(lines)


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

    report = reasoner.reason(question, result, profile=profile, history=convo)
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
