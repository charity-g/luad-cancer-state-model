from __future__ import annotations

from typing import Any

from backend.agents.create_graph.model import ProteinRecord, MutationProteinEffect


def extract_protein_for_mutation(mutation: MutationProteinEffect) -> ProteinRecord:
    protein_id = str(mutation.protein or "").strip()
    if not protein_id:
        raise ValueError("Unable to determine protein for mutation")

    identifiers = mutation.identifiers or {}
    gene_symbol = str(identifiers.get("gene_symbol") or protein_id)

    return ProteinRecord(
        query=protein_id,
        gene_symbol=gene_symbol,
        uniprot_id=identifiers.get("uniprot_ac") or identifiers.get("uniprot_id"),
        entrez_gene_id=identifiers.get("entrez_gene_id"),
        kegg_gene_id=identifiers.get("kegg_gene_id"),
        kegg_ko_id=identifiers.get("kegg_ko_id"),
        kegg_description=identifiers.get("kegg_description"),
        source="mutation-profile",
        raw_response=None,
    )


def extract_pathways_for_protein(protein: ProteinRecord) -> list[dict[str, Any]]:
    protein_id = (
        protein.kegg_gene_id
        or protein.kegg_ko_id
        or protein.uniprot_id
        or protein.gene_symbol
        or protein.query
    )
    return [
        {
            "kegg_id": protein_id,
            "name": protein.gene_symbol or protein.query,
            "evidence": protein.kegg_description or "no_effect",
        }
    ]


def fetch_pathway_information(pathway: dict[str, Any]) -> dict[str, Any]:
    return {
        "kegg_id": pathway.get("kegg_id", ""),
        "name": pathway.get("name", ""),
        "evidence": pathway.get("evidence", "no_effect"),
        "source": "upload-profile-stream",
    }
