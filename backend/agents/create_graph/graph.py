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


def init_graph(profile_id: str) -> list:
    """Create constraints/indexes and upsert the Profile node for profile_id."""
    api = _get_api()
    statements = [
        "CREATE CONSTRAINT profile_id IF NOT EXISTS FOR (prof:Profile) REQUIRE prof.profile_id IS UNIQUE",
        "CREATE CONSTRAINT protein_kegg_id IF NOT EXISTS FOR (p:Protein) REQUIRE p.kegg_id IS UNIQUE",
        "CREATE CONSTRAINT mutation_id IF NOT EXISTS FOR (m:Mutation) REQUIRE m.mutation_id IS UNIQUE",
        "CREATE CONSTRAINT pathway_kegg_id IF NOT EXISTS FOR (pw:Pathway) REQUIRE pw.kegg_id IS UNIQUE",
        "CREATE CONSTRAINT pathway_entry_kegg_id IF NOT EXISTS FOR (pe:PathwayEntry) REQUIRE pe.kegg_id IS UNIQUE",
    ]
    results = []
    for stmt in statements:
        try:
            api.execute(stmt)
            results.append({"statement": stmt, "status": "ok"})
        except RuntimeError as e:
            results.append({"statement": stmt, "status": "skipped", "reason": str(e)})

    api.execute(
        "MERGE (prof:Profile {profile_id: $pid}) ON CREATE SET prof.created_at = timestamp()",
        {"pid": profile_id},
    )
    return results


def add_mutation_node(mutation: MutationProteinEffect, profile_id: str) -> dict[str, Any]:
    """Upsert a Mutation node and link it to the Profile subgraph."""
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
    WITH m
    MATCH (prof:Profile {profile_id: $profile_id})
    MERGE (prof)-[:HAS_MUTATION]->(m)
    RETURN m
    """
    params = {
        "mutation_id": mutation.mutation_id,
        "protein": mutation.protein,
        "identifiers": json.dumps(mutation.identifiers),
        "estimated_effect": mutation.estimated_effect,
        "confidence": mutation.confidence,
        "justification": json.dumps(mutation.justification),
        "profile_id": profile_id,
    }
    payload = api.execute(cypher, params)
    data = payload.get("data", {})
    values = data.get("values", [])
    return values[0][0].get("properties", {}) if values else params


def add_protein_node(protein: ProteinRecord, profile_id: str) -> dict[str, Any]:
    """Upsert a Protein node and link it to the Profile subgraph."""
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
    WITH p
    MATCH (prof:Profile {profile_id: $profile_id})
    MERGE (prof)-[:HAS_PROTEIN]->(p)
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
        "profile_id": profile_id,
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


_PROMOTES = {"activation", "expression", "phosphorylation", "indirect effect", "glycosylation"}
_INHIBITS  = {"inhibition", "repression", "dephosphorylation", "ubiquitination", "methylation"}


def _link_profile_and_mutations(api, pathway_id: str, profile_id: str) -> None:
    """Link an already-existing Pathway to the Profile, and wire any profile
    Protein nodes that match pathway entries to the pathway via INVOLVED_IN."""
    api.execute(
        """
        MATCH (pw:Pathway {kegg_id: $kegg_id})
        MATCH (prof:Profile {profile_id: $profile_id})
        MERGE (prof)-[:HAS_PATHWAY]->(pw)
        """,
        {"kegg_id": pathway_id, "profile_id": profile_id},
    )
    # For each Protein in this profile that matches a PathwayEntry in this pathway,
    # ensure INVOLVED_IN exists (idempotent — safe to re-run).
    try:
        api.execute(
            """
            MATCH (prof:Profile {profile_id: $profile_id})-[:HAS_PROTEIN]->(p:Protein)
            MATCH (pw:Pathway {kegg_id: $kegg_id})
            WHERE (p.kegg_gene_id IS NOT NULL OR p.kegg_ko_id IS NOT NULL)
            AND EXISTS {
                MATCH (pw)-[:PATHWAY_ENTRY]->(pe:PathwayEntry)
                WHERE pe.identifiers CONTAINS p.kegg_gene_id
                   OR pe.identifiers CONTAINS p.kegg_ko_id
            }
            MERGE (p)-[:INVOLVED_IN]->(pw)
            """,
            {"profile_id": profile_id, "kegg_id": pathway_id},
        )
    except RuntimeError:
        pass


def add_pathway_information(pathway: dict[str, Any], profile_id: str) -> dict[str, Any]:
    """
    Persist a KEGG pathway into the graph, or reuse it if already present.

    If the Pathway node (kegg_id) already exists:
      - Link it to the Profile via HAS_PATHWAY
      - Link profile Protein nodes to it via INVOLVED_IN (where kegg_id matches)
      - Skip all KGML parsing/entry/edge writes (pathway structure is shared)

    If the Pathway node does not yet exist, do a full build:
      - Pathway node + HAS_PATHWAY to Profile
      - PathwayEntry nodes + PATHWAY_ENTRY edges
      - INVOLVED_IN edges for matching profile Proteins
      - PATHWAY_RELATION edges between PathwayEntry nodes
      - PROMOTES / INHIBITS edges between matched Protein nodes
      - ACTIVATES_PATHWAY / INHIBITS_PATHWAY from Protein → cross-referenced Pathway
    """
    api = _get_api()
    pathway_id = pathway.get("pathway_id", "")
    title = pathway.get("pathway_title", pathway_id)

    # Check whether this pathway is already fully built in the graph.
    existing = api.execute(
        "MATCH (pw:Pathway {kegg_id: $kegg_id}) RETURN count(pw) AS n",
        {"kegg_id": pathway_id},
    )
    already_exists = (
        existing.get("data", {}).get("values", [[0]])[0][0] or 0
    ) > 0

    if already_exists:
        _link_profile_and_mutations(api, pathway_id, profile_id)
        return {
            "pathway_id": pathway_id,
            "name": title,
            "total_nodes": pathway.get("total_nodes", 0),
            "total_edges": pathway.get("total_edges", 0),
            "status": "linked",
        }

    # ── Full build ────────────────────────────────────────────────────────────

    # 1. Create Pathway node and link to Profile
    api.execute(
        """
        MERGE (pw:Pathway {kegg_id: $kegg_id})
        ON CREATE SET pw.name = $name, pw.created_at = timestamp()
        ON MATCH  SET pw.name = $name
        WITH pw
        MATCH (prof:Profile {profile_id: $profile_id})
        MERGE (prof)-[:HAS_PATHWAY]->(pw)
        """,
        {"kegg_id": pathway_id, "name": title, "profile_id": profile_id},
    )

    # 2. PathwayEntry nodes + INVOLVED_IN for matching Proteins
    for entry in pathway.get("nodes", {}).values():
        entry_id = entry.get("entry_id", "")
        if not entry_id:
            continue
        node_kegg_id = f"{pathway_id}:{entry_id}"
        api.execute(
            """
            MERGE (pe:PathwayEntry {kegg_id: $kegg_id})
            ON CREATE SET
                pe.entry_id     = $entry_id,
                pe.type         = $type,
                pe.display_name = $display_name,
                pe.identifiers  = $identifiers,
                pe.created_at   = timestamp()
            ON MATCH SET
                pe.type         = $type,
                pe.display_name = $display_name,
                pe.identifiers  = $identifiers
            WITH pe
            MATCH (pw:Pathway {kegg_id: $pathway_kegg_id})
            MERGE (pw)-[:PATHWAY_ENTRY]->(pe)
            """,
            {
                "kegg_id":          node_kegg_id,
                "entry_id":         entry_id,
                "type":             entry.get("type", ""),
                "display_name":     entry.get("display_name", ""),
                "identifiers":      json.dumps(entry.get("kegg_identifiers", [])),
                "pathway_kegg_id":  pathway_id,
            },
        )
        for kegg_name in entry.get("kegg_identifiers", []):
            try:
                api.execute(
                    """
                    MATCH (p:Protein)
                    WHERE p.kegg_gene_id = $kegg_name OR p.kegg_ko_id = $kegg_name
                    MATCH (pw:Pathway {kegg_id: $pathway_kegg_id})
                    MERGE (p)-[:INVOLVED_IN]->(pw)
                    """,
                    {"kegg_name": kegg_name, "pathway_kegg_id": pathway_id},
                )
            except RuntimeError:
                pass

    nodes_by_entry: dict[str, dict] = {
        str(e.get("entry_id", "")): e
        for e in pathway.get("nodes", {}).values()
        if e.get("entry_id")
    }

    # 3. PATHWAY_RELATION edges between PathwayEntry nodes
    for edge in pathway.get("edges", []):
        src_kegg_id = f"{pathway_id}:{edge.get('source_id', '')}"
        tgt_kegg_id = f"{pathway_id}:{edge.get('target_id', '')}"
        if not edge.get("source_id") or not edge.get("target_id"):
            continue
        try:
            api.execute(
                """
                MATCH (src:PathwayEntry {kegg_id: $src})
                MATCH (tgt:PathwayEntry {kegg_id: $tgt})
                MERGE (src)-[r:PATHWAY_RELATION {relation_type: $rel_type}]->(tgt)
                ON CREATE SET r.mechanisms = $mechanisms, r.created_at = timestamp()
                ON MATCH  SET r.mechanisms = $mechanisms
                """,
                {
                    "src":       src_kegg_id,
                    "tgt":       tgt_kegg_id,
                    "rel_type":  edge.get("relation_type", ""),
                    "mechanisms": json.dumps(edge.get("mechanisms", [])),
                },
            )
        except RuntimeError:
            pass

    # 4. Protein→Protein (PROMOTES/INHIBITS) and Protein→Pathway (ACTIVATES/INHIBITS_PATHWAY)
    for edge in pathway.get("edges", []):
        src_id = str(edge.get("source_id", ""))
        tgt_id = str(edge.get("target_id", ""))
        if not src_id or not tgt_id:
            continue

        raw_mechs: list[dict] = edge.get("mechanisms", [])
        mech_names: set[str] = {m.get("mechanism", "") for m in raw_mechs if isinstance(m, dict)}
        mechs_json = json.dumps([m.get("mechanism", "") for m in raw_mechs if isinstance(m, dict)])

        promotes = bool(mech_names & _PROMOTES)
        inhibits = bool(mech_names & _INHIBITS)
        rel_type = "INHIBITS" if inhibits and not promotes else "PROMOTES"

        src_node = nodes_by_entry.get(src_id, {})
        tgt_node = nodes_by_entry.get(tgt_id, {})
        src_ids  = src_node.get("kegg_identifiers", [])
        tgt_ids  = tgt_node.get("kegg_identifiers", [])
        tgt_type = tgt_node.get("type", "")

        if not src_ids:
            continue

        # 4a. Protein → Protein
        if tgt_ids and tgt_type != "map":
            try:
                api.execute(
                    f"""
                    MATCH (src:Protein)
                    WHERE any(id IN $src_ids WHERE src.kegg_gene_id = id OR src.kegg_ko_id = id)
                    MATCH (tgt:Protein)
                    WHERE any(id IN $tgt_ids WHERE tgt.kegg_gene_id = id OR tgt.kegg_ko_id = id)
                      AND src <> tgt
                    MERGE (src)-[r:{rel_type} {{pathway_id: $pathway_id}}]->(tgt)
                    ON CREATE SET r.mechanisms = $mechanisms, r.created_at = timestamp()
                    ON MATCH  SET r.mechanisms = $mechanisms
                    """,
                    {
                        "src_ids":    src_ids,
                        "tgt_ids":    tgt_ids,
                        "pathway_id": pathway_id,
                        "mechanisms": mechs_json,
                    },
                )
            except RuntimeError:
                pass

        # 4b. Protein → Pathway (map cross-reference entries)
        if tgt_type == "map":
            pw_rel = "INHIBITS_PATHWAY" if rel_type == "INHIBITS" else "ACTIVATES_PATHWAY"
            for kegg_ref in tgt_ids:
                ref_id = kegg_ref.replace("path:", "")
                try:
                    api.execute(
                        f"""
                        MATCH (src:Protein)
                        WHERE any(id IN $src_ids WHERE src.kegg_gene_id = id OR src.kegg_ko_id = id)
                        MATCH (pw:Pathway {{kegg_id: $ref_id}})
                        MERGE (src)-[r:{pw_rel} {{pathway_id: $pathway_id}}]->(pw)
                        ON CREATE SET r.mechanisms = $mechanisms, r.created_at = timestamp()
                        ON MATCH  SET r.mechanisms = $mechanisms
                        """,
                        {
                            "src_ids":    src_ids,
                            "ref_id":     ref_id,
                            "pathway_id": pathway_id,
                            "mechanisms": mechs_json,
                        },
                    )
                except RuntimeError:
                    pass

    return {
        "pathway_id": pathway_id,
        "name": title,
        "total_nodes": pathway.get("total_nodes", 0),
        "total_edges": pathway.get("total_edges", 0),
        "status": "upserted",
    }


def update_pathway(pathway_information: dict[str, Any], profile_id: str) -> dict[str, Any]:
    return add_pathway_information(pathway_information, profile_id)
