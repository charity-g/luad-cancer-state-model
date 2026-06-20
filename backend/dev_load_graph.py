#!/usr/bin/env python3
"""DEV-ONLY loader: populate local Neo4j from luad_perturbation_layer.json.

This exists so the backend can be developed/tested against the team's
multi-source schema (Gene / Pathway / Mutation + perturbation edges) as
documented in scripts/init_neo4j/NEO4J_SCHEMA.md. The *canonical* loader is the
team's scripts/init_neo4j/ (schema.cypher + upload_init.py); this is a stopgap
that loads the same schema from the self-contained perturbation-layer JSON so
local work isn't blocked. Idempotent: wipes and rebuilds.

    python -m backend.dev_load_graph
"""

import json
from pathlib import Path

from neo4j import GraphDatabase

from backend.config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD

ROOT = Path(__file__).resolve().parents[1]
GRAPH_JSON = ROOT / "pathways" / "luad_perturbation_layer.json"

NODE_LABELS = {"pathway": "Pathway", "gene": "Gene", "mutation": "Mutation"}

# JSON edge "type" -> Neo4j relationship type (matches NEO4J_SCHEMA.md).
REL_TYPES = {
    "activates": "ACTIVATES_PATHWAY",
    "represses": "REPRESSES_PATHWAY",
    "shared_DEG": "SHARES_DEG_WITH",
    "downstream_of": "DOWNSTREAM_OF",
    "crosstalk": "CROSSTALK_WITH",
    "mutates": "MUTATES",
    "member_of": "MEMBER_OF",
    "perturbs": "PERTURBS",
    "crispr_validates": "CRISPR_VALIDATES",
}


def _clean(props):
    """Neo4j stores only primitives / arrays of primitives. JSON-encode the rest
    (e.g. pathway top_perturbations_luad, a list of dicts)."""
    out = {}
    for k, v in props.items():
        if isinstance(v, (str, int, float, bool)) or v is None:
            out[k] = v
        elif isinstance(v, list) and all(
            isinstance(i, (str, int, float, bool)) for i in v
        ):
            out[k] = v
        else:
            out[k] = json.dumps(v)
    return out


def main():
    data = json.loads(GRAPH_JSON.read_text())
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    try:
        driver.verify_connectivity()
        with driver.session() as s:
            s.run("MATCH (n) DETACH DELETE n")
            # Match-key index on the JSON id (edges reference nodes by it).
            for label in NODE_LABELS.values():
                s.run(f"CREATE INDEX {label.lower()}_id IF NOT EXISTS FOR (n:{label}) ON (n.id)")

            nodes = data["pathway_nodes"] + data["gene_nodes"] + data["mutation_nodes"]
            for n in nodes:
                label = NODE_LABELS[n["type"]]
                props = _clean(n)
                # NEO4J_SCHEMA.md documents Mutation.gene_symbol, but the source
                # JSON stores it as `gene`. Alias it so queries match the schema doc.
                if label == "Mutation" and "gene" in n:
                    props.setdefault("gene_symbol", n["gene"])
                s.run(f"MERGE (x:{label} {{id: $id}}) SET x += $props", id=n["id"], props=props)
            print(f"Loaded {len(nodes)} nodes")

            edges = data["pathway_edges"] + data["perturbation_edges"]
            loaded = 0
            for e in edges:
                rel = REL_TYPES.get(e["type"])
                if rel is None:
                    print(f"WARNING: unmapped edge type {e['type']!r}; skipping")
                    continue
                props = _clean({k: v for k, v in e.items() if k not in ("source", "target")})
                s.run(
                    f"MATCH (a {{id: $source}}) MATCH (b {{id: $target}}) "
                    f"MERGE (a)-[r:{rel}]->(b) SET r += $props",
                    source=e["source"], target=e["target"], props=props,
                )
                loaded += 1
            print(f"Loaded {loaded} edges")

            counts = {
                r["l"]: r["c"]
                for r in s.run("MATCH (n) UNWIND labels(n) AS l RETURN l, count(*) AS c")
            }
            rels = s.run("MATCH ()-[r]->() RETURN count(r) AS c").single()["c"]
            print("Node labels:", counts, "| relationships:", rels)
    finally:
        driver.close()


if __name__ == "__main__":
    main()
