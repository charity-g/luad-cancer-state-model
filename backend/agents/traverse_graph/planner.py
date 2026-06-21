"""Planner — turns a natural-language question into a read-only Cypher query.

Primary path (text2Cypher): Claude generates Cypher, grounded by the authoritative
NEO4J_SCHEMA.md. The output is validated as read-only before it reaches the DB.

Fallback path (no API key, or generation fails/produces a write): a deterministic
query built from entities resolved against the graph vocabulary, using the
schema's documented traversal patterns. This keeps the pipeline runnable without
an LLM while matching the team's schema.
"""

import re
from functools import lru_cache

import anthropic

from backend.agents.traverse_graph import cypher
from backend.config import ANTHROPIC_API_KEY, PLANNER_MODEL

_INTERVENTION = re.compile(
    r"\b(inhibit|block|suppress|knock|knockout|knockdown|target|drug|treat|"
    r"reverse|activat|overexpress|effect|help|improve|resist|combination)\b", re.I
)

# Questions that are pure information retrieval — answer with graph + short summary,
# no mechanistic reasoning needed.
_LOOKUP = re.compile(
    r"\b(show|list|what\s+is|what\s+are|which|find|get|display|give\s+me|"
    r"how\s+many|where|fetch|return|pull|map|visuali[sz]e|graph\s+of|"
    r"network\s+of|who|tell\s+me\s+about|describe|connections?\s+of|"
    r"neighbors?\s+of|connected\s+to|related\s+to)\b",
    re.I,
)


def classify(question: str) -> str:
    """Return 'lookup' when the question is pure information retrieval, 'reason' otherwise.

    Lookup: user wants to SEE a graph (nodes/edges pulled from DB).
    Reason: user wants mechanistic analysis, intervention evaluation, or causal inference.
    Intervention signals always win — 'show me what drugs inhibit EGFR' is 'reason'.
    """
    if _LOOKUP.search(question) and not _INTERVENTION.search(question):
        return "lookup"
    return "reason"

_PLANNER_SYSTEM = (
    "You translate questions about a LUAD (lung adenocarcinoma) causal biology "
    "Neo4j graph into a SINGLE read-only Cypher query. Use ONLY the labels, "
    "properties, and relationship types defined in the schema below. The query "
    "must be read-only: no CREATE, MERGE, SET, DELETE, REMOVE. Return graph "
    "entities (nodes and relationships) where possible so the result can be "
    "visualized. Output ONLY the Cypher query — no prose, no markdown fences.\n\n"
    "=== SCHEMA ===\n" + cypher.schema_text()
)


def plan(question, profile="", history=""):
    if ANTHROPIC_API_KEY:
        try:
            cy = _plan_llm(question, profile, history)
            if cy and cypher.is_read_only(cy):
                return {"cypher": cy, "params": {}, "source": "llm"}
        except Exception:
            pass
    cy, params = _fallback(question)
    return {"cypher": cy, "params": params, "source": "fallback"}


# --- text2Cypher ----------------------------------------------------------

def _plan_llm(question, profile="", history=""):
    client = anthropic.Anthropic()
    # Ground the planner in what's actually loaded — the schema doc describes the
    # full target schema, but only a subset may be populated.
    system = (
        _PLANNER_SYSTEM
        + "\n\n=== CURRENTLY LOADED (query only these) ===\n"
        + cypher.graph_summary()
    )
    # Profile (sample mutations) helps target the right genes; history lets the
    # query resolve follow-ups like "what about its downstream targets?".
    user = question
    if profile:
        user = f"{profile}\n\nQuestion: {question}"
    if history:
        user = f"Recent conversation:\n{history}\n\n{user}"
    resp = client.messages.create(
        model=PLANNER_MODEL,
        max_tokens=600,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    text = "".join(b.text for b in resp.content if b.type == "text").strip()
    return _strip_fences(text)


def _strip_fences(text):
    m = re.search(r"```(?:cypher)?\s*(.+?)```", text, re.S | re.I)
    return (m.group(1) if m else text).strip()


# --- deterministic fallback ----------------------------------------------

@lru_cache(maxsize=1)
def _vocab():
    genes = cypher.run_read(
        "MATCH (g:Gene) WHERE g.symbol IS NOT NULL RETURN collect(g.symbol) AS x"
    )["rows"][0]["x"]
    mut = cypher.run_read("MATCH (m:Mutation) RETURN collect(m.id) AS x")["rows"][0]["x"]
    # Only pathways with a snake_case id can anchor a fallback query.
    paths = cypher.run_read(
        "MATCH (p:Pathway) WHERE p.id IS NOT NULL "
        "RETURN collect({id: p.id, label: p.label, title: p.title}) AS x"
    )["rows"][0]["x"]
    return {"genes": set(genes), "mutations": mut, "pathways": paths}


def _matches(p, q):
    # Match the question against the pathway's label or KEGG title.
    for field in (p.get("label"), p.get("title")):
        if field and field.lower().replace("kegg ", "") in q:
            return True
    return False


def _fallback(question):
    vocab = _vocab()
    tokens = {t.upper() for t in re.findall(r"[A-Za-z0-9]+", question)}
    genes = sorted(tokens & vocab["genes"])
    q = question.lower()
    pathways = [p["id"] for p in vocab["pathways"] if _matches(p, q)]

    # Intervention question about a gene -> mutation/gene -> pathway cascade + essentiality.
    if genes and _INTERVENTION.search(question):
        return (
            "MATCH (g:Gene {symbol: $sym}) "
            "OPTIONAL MATCH (m:Mutation)-[mut:MUTATES]->(g) "
            "OPTIONAL MATCH (g)-[mem:MEMBER_OF]->(p:Pathway) "
            "OPTIONAL MATCH (m)-[pert:PERTURBS]->(p) "
            "RETURN g, m, mut, p, mem, pert",
            {"sym": genes[0]},
        )
    if genes:
        return (
            "MATCH (g:Gene {symbol: $sym}) "
            "OPTIONAL MATCH (g)-[mem:MEMBER_OF]->(p:Pathway) "
            "RETURN g, mem, p",
            {"sym": genes[0]},
        )
    if pathways:
        return (
            "MATCH (p:Pathway {id: $pid}) "
            "OPTIONAL MATCH (p)-[r]-(q:Pathway) "
            "OPTIONAL MATCH (g:Gene)-[mem:MEMBER_OF]->(p) WHERE g.is_essential_luad "
            "RETURN p, r, q, g, mem",
            {"pid": pathways[0]},
        )
    # Nothing resolved -> overview of the most active pathways.
    return (
        "MATCH (p:Pathway) WHERE p.status = 'activated' "
        "WITH p ORDER BY p.deg_count DESC LIMIT 5 "
        "OPTIONAL MATCH (p)-[r:ACTIVATES_PATHWAY|DOWNSTREAM_OF]->(q:Pathway) "
        "RETURN p, r, q",
        {},
    )
