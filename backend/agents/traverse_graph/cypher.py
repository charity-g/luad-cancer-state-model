

"""Read-only Cypher execution layer over the LUAD Neo4j graph.

The planner generates Cypher; this module executes it safely (read-only guard)
and normalizes the result into JSON-serializable rows plus a {nodes, edges}
subgraph for the frontend. It also exposes the schema doc used to ground the
planner's Cypher generation.
"""

import re
from functools import lru_cache
from pathlib import Path

import backend.neo4j_http as neo4j_http

ROOT = Path(__file__).resolve().parents[3]
SCHEMA_DOC = ROOT / "scripts" / "init_neo4j" / "NEO4J_SCHEMA.md"

# Reject anything that could mutate the graph — the LLM only ever reads.
_FORBIDDEN = re.compile(
    r"\b(CREATE|MERGE|DELETE|REMOVE|SET|DROP|DETACH|FOREACH|LOAD\s+CSV)\b", re.I
)


@lru_cache(maxsize=1)
def schema_text():
    return SCHEMA_DOC.read_text(encoding="utf-8")


def is_read_only(cypher):
    return _FORBIDDEN.search(cypher) is None


def run_read(cypher, params=None):
    """Execute a read-only query via the HTTP Query API.

    Returns {rows, subgraph}.
    """
    if not is_read_only(cypher):
        raise ValueError("Refusing to run non-read-only Cypher")
    return neo4j_http.run_read(cypher, params)


def full_graph():
    """Entire graph for the frontend's static visualization (incl. isolated nodes)."""
    return run_read("MATCH (n) OPTIONAL MATCH (n)-[r]->(m) RETURN n, r, m")["subgraph"]


def graph_summary():
    """Labels + relationship types actually present, with counts. Grounds the
    planner so the LLM only generates queries against structure that exists."""
    labels = run_read(
        "MATCH (n) UNWIND labels(n) AS l RETURN l AS k, count(*) AS c ORDER BY c DESC"
    )["rows"]
    rels = run_read(
        "MATCH ()-[r]->() RETURN type(r) AS k, count(*) AS c ORDER BY c DESC"
    )["rows"]
    fmt = lambda rows: ", ".join(f"{r['k']}({r['c']})" for r in rows)
    return f"Node labels: {fmt(labels)}\nRelationship types: {fmt(rels)}"
