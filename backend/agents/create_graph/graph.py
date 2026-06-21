from __future__ import annotations

import json
from typing import Any

from backend.agents.create_graph.model import ProteinRecord, MutationProteinEffect
from backend.neo4j_http import _get_api


def _protein_graph_id(protein: ProteinRecord) -> str:
    return (
        protein.kegg_gene_id
        or protein.kegg_ko_id
        or protein.uniprot_id
        or protein.gene_symbol
        or protein.query
    )


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
        m.identifiers      = $identifiers,
        m.estimated_effect = $estimated_effect,
        m.confidence       = $confidence,
        m.justification    = $justification,
        m.created_at       = timestamp()
    ON MATCH SET
        m.protein          = $protein,
        m.identifiers      = $identifiers,
        m.estimated_effect = $estimated_effect,
        m.confidence       = $confidence,
        m.justification    = $justification,
        m.updated_at       = timestamp()
    RETURN m
    """
    params = {
        "mutation_id": mutation.mutation_id,
        "protein": mutation.protein,
        "identifiers": json.dumps(mutation.identifiers),
        "estimated_effect": mutation.estimated_effect,
        "confidence": mutation.confidence,
        "justification": json.dumps(mutation.justification),
    }
    payload = api.execute(cypher, params)
    data = payload.get("data", {})
    values = data.get("values", [])
    return values[0][0].get("properties", {}) if values else params


def add_protein_node(protein: ProteinRecord) -> dict[str, Any]:
    """Upsert a Protein node (wild-type when no mutation is associated)."""
    api = _get_api()
    kegg_id = _protein_graph_id(protein)
    cypher = """
    MERGE (p:Protein {kegg_id: $kegg_id})
    ON CREATE SET
        p.query            = $query,
        p.gene_symbol      = $gene_symbol,
        p.uniprot_id       = $uniprot_id,
        p.entrez_gene_id   = $entrez_gene_id,
        p.kegg_gene_id     = $kegg_gene_id,
        p.kegg_ko_id       = $kegg_ko_id,
        p.kegg_description = $kegg_description,
        p.source           = $source,
        p.raw_response     = $raw_response,
        p.created_at       = timestamp()
    ON MATCH SET
        p.query            = $query,
        p.gene_symbol      = $gene_symbol,
        p.uniprot_id       = $uniprot_id,
        p.entrez_gene_id   = $entrez_gene_id,
        p.kegg_gene_id     = $kegg_gene_id,
        p.kegg_ko_id       = $kegg_ko_id,
        p.kegg_description = $kegg_description,
        p.source           = $source,
        p.raw_response     = $raw_response,
        p.updated_at       = timestamp()
    RETURN p
    """
    params = {
        "kegg_id": kegg_id,
        "query": protein.query,
        "gene_symbol": protein.gene_symbol,
        "uniprot_id": protein.uniprot_id,
        "entrez_gene_id": protein.entrez_gene_id,
        "kegg_gene_id": protein.kegg_gene_id,
        "kegg_ko_id": protein.kegg_ko_id,
        "kegg_description": protein.kegg_description,
        "source": protein.source,
        "raw_response": protein.raw_response,
    }
    payload = api.execute(cypher, params)
    data = payload.get("data", {})
    values = data.get("values", [])
    return values[0][0].get("properties", {}) if values else params


def link_mutation_to_protein(mutation: MutationProteinEffect, protein: ProteinRecord) -> None:
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
        "mutation_id": mutation.mutation_id,
        "kegg_id": _protein_graph_id(protein),
        "estimated_effect": mutation.estimated_effect,
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
