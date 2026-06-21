from __future__ import annotations

from typing import Any

from backend.agents.create_graph.model import ProteinRecord, MutationProteinEffect
from backend.neo4j_http import _get_api


def init_graph() -> list:
    """Create constraints and indexes for the graph schema."""
    api = _get_api()
    statements = [
        "CREATE CONSTRAINT protein_kegg_id IF NOT EXISTS FOR (p:Protein) REQUIRE p.kegg_id IS UNIQUE",
        "CREATE CONSTRAINT mutation_id IF NOT EXISTS FOR (m:Mutation) REQUIRE m.mutation_id IS UNIQUE",
        "CREATE CONSTRAINT pathway_kegg_id IF NOT EXISTS FOR (pw:Pathway) REQUIRE pw.kegg_id IS UNIQUE",
    ]
    results = []
    for stmt in statements:
        try:
            api.execute(stmt)
            results.append({"statement": stmt, "status": "ok"})
        except RuntimeError as e:
            results.append({"statement": stmt, "status": "skipped", "reason": str(e)})
    return results


def add_mutation_node(mutation: MutationProteinEffect) -> dict[str, Any]:
    """Upsert a Mutation node. Returns the stored properties."""
    api = _get_api()
    cypher = """
    MERGE (m:Mutation {mutation_id: $mutation_id})
    ON CREATE SET
        m.protein          = $protein,
        m.estimated_effect = $estimated_effect,
        m.created_at       = timestamp()
    ON MATCH SET
        m.protein          = $protein,
        m.estimated_effect = $estimated_effect,
        m.updated_at       = timestamp()
    RETURN m
    """
    params = {
        "mutation_id": mutation.get("mutation_id", ""),
        "protein": mutation.get("protein", ""),
        "estimated_effect": mutation.get("estimated_effect", "Unknown effect"),
    }
    payload = api.execute(cypher, params)
    data = payload.get("data", {})
    values = data.get("values", [])
    return values[0][0].get("properties", {}) if values else params


def add_protein_node(protein: ProteinRecord) -> dict[str, Any]:
    """Upsert a Protein node (wild-type when no mutation is associated)."""
    api = _get_api()
    cypher = """
    MERGE (p:Protein {kegg_id: $kegg_id})
    ON CREATE SET
        p.ids        = $ids,
        p.semantic   = $semantic,
        p.created_at = timestamp()
    ON MATCH SET
        p.ids        = $ids,
        p.semantic   = $semantic,
        p.updated_at = timestamp()
    RETURN p
    """
    import json
    params = {
        "kegg_id": protein.kegg_id,
        "ids": json.dumps(protein.ids),
        "semantic": json.dumps(protein.semantic),
    }
    payload = api.execute(cypher, params)
    data = payload.get("data", {})
    values = data.get("values", [])
    return values[0][0].get("properties", {}) if values else params


def _link_mutation_to_protein(mutation_id: str, kegg_id: str, estimated_effect: str) -> None:
    """Create a AFFECTS edge between a Mutation and a Protein."""
    api = _get_api()
    cypher = """
    MATCH (m:Mutation {mutation_id: $mutation_id})
    MATCH (p:Protein  {kegg_id:     $kegg_id})
    MERGE (m)-[r:AFFECTS]->(p)
    ON CREATE SET r.estimated_effect = $estimated_effect, r.created_at = timestamp()
    ON MATCH  SET r.estimated_effect = $estimated_effect
    """
    api.execute(cypher, {
        "mutation_id": mutation_id,
        "kegg_id": kegg_id,
        "estimated_effect": estimated_effect,
    })


def add_pathway_information(pathway: dict[str, Any]) -> dict[str, Any]:
    """Upsert a Pathway node and link it to its Protein via INVOLVED_IN."""
    api = _get_api()

    # Upsert the Pathway node
    upsert_cypher = """
    MERGE (pw:Pathway {kegg_id: $kegg_id})
    ON CREATE SET pw.name = $name, pw.created_at = timestamp()
    ON MATCH  SET pw.name = $name
    RETURN pw
    """
    params = {
        "kegg_id": pathway.get("kegg_id", ""),
        "name": pathway.get("name", pathway.get("kegg_id", "")),
    }
    api.execute(upsert_cypher, params)

    # Link Protein -> Pathway when a protein kegg_id is present
    protein_kegg_id = pathway.get("kegg_id", "")
    evidence = pathway.get("evidence", "no_effect")
    if protein_kegg_id:
        link_cypher = """
        MATCH (p:Protein {kegg_id: $protein_kegg_id})
        MATCH (pw:Pathway {kegg_id: $pathway_kegg_id})
        MERGE (p)-[r:INVOLVED_IN]->(pw)
        ON CREATE SET r.evidence = $evidence, r.created_at = timestamp()
        ON MATCH  SET r.evidence = $evidence
        """
        try:
            api.execute(link_cypher, {
                "protein_kegg_id": protein_kegg_id,
                "pathway_kegg_id": protein_kegg_id,
                "evidence": evidence,
            })
        except RuntimeError:
            # Protein may not yet exist; caller should ensure add_protein_node runs first.
            pass

    return {"kegg_id": params["kegg_id"], "name": params["name"], "status": "upserted"}


def update_pathway(pathway_information: dict[str, Any]) -> dict[str, Any]:
    return add_pathway_information(pathway_information)
