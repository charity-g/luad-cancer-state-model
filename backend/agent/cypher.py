"""Read-only Cypher execution layer over the LUAD Neo4j graph.

The planner generates Cypher; this module executes it safely (read-only guard)
and normalizes the result into JSON-serializable rows plus a {nodes, edges}
subgraph for the frontend. It also exposes the schema doc used to ground the
planner's Cypher generation.
"""

import re
from functools import lru_cache
from pathlib import Path

from neo4j import GraphDatabase
from neo4j.graph import Node, Relationship

from backend.config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_DOC = ROOT / "scripts" / "init_neo4j" / "NEO4J_SCHEMA.md"

# Reject anything that could mutate the graph — the LLM only ever reads.
_FORBIDDEN = re.compile(
    r"\b(CREATE|MERGE|DELETE|REMOVE|SET|DROP|DETACH|FOREACH|LOAD\s+CSV)\b", re.I
)

_driver = None


def driver():
    global _driver
    if _driver is None:
        _driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    return _driver


@lru_cache(maxsize=1)
def schema_text():
    return SCHEMA_DOC.read_text(encoding="utf-8")


def is_read_only(cypher):
    return _FORBIDDEN.search(cypher) is None


def _scalar(v):
    if isinstance(v, Node):
        return {"id": v.get("id"), "labels": list(v.labels), **dict(v)}
    if isinstance(v, Relationship):
        return {"type": v.type, **dict(v)}
    return v


def _subgraph(graph):
    nodes = [
        {"id": n.get("id"), "labels": list(n.labels), **dict(n)} for n in graph.nodes
    ]
    edges = [
        {
            "type": r.type,
            "source": r.start_node.get("id") if r.start_node else None,
            "target": r.end_node.get("id") if r.end_node else None,
            **dict(r),
        }
        for r in graph.relationships
    ]
    return {"nodes": nodes, "edges": edges}


def run_read(cypher, params=None):
    """Execute a read-only query. Raises ValueError if it isn't read-only.

    Returns {rows, subgraph} — rows are the raw result (nodes/rels flattened to
    dicts); subgraph is built from any graph entities the query returned.
    """
    if not is_read_only(cypher):
        raise ValueError("Refusing to run non-read-only Cypher")
    with driver().session() as session:
        result = session.run(cypher, **(params or {}))
        rows = [{k: _scalar(v) for k, v in rec.items()} for rec in result]
        subgraph = _subgraph(result.graph())
    return {"rows": rows, "subgraph": subgraph}


def full_graph():
    """Entire graph for the frontend's static visualization (incl. isolated nodes)."""
    return run_read("MATCH (n) OPTIONAL MATCH (n)-[r]->(m) RETURN n, r, m")["subgraph"]
