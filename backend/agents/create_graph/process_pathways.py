from __future__ import annotations

from typing import Any

from backend.agents.create_graph.model import ProteinRecord, MutationProteinEffect


def extract_protein_for_mutation(mutation: MutationProteinEffect) -> ProteinRecord:

    # call requests if there is a relevant protein, map mutation to protein
    # https://rest.kegg.jp/find/genes/EGFR
    # otherwise raise error a
    
        protein_id = str(getattr(mutation, "protein", "") or "").strip()
        if not protein_id:
            raise ValueError("Unable to determine protein for mutation")

        identifiers = getattr(mutation, "identifiers", {}) or {}
        gene_symbol = identifiers.get("gene_symbol") or protein_id

        return ProteinRecord(
            kegg_id=protein_id,
            ids={
                "protein_symbol": str(gene_symbol),
                "mutation_id": str(getattr(mutation, "mutation_id", "")),
            },
            semantic={
                "estimated_effect": getattr(mutation, "estimated_effect", "uncertain"),
                "confidence": getattr(mutation, "confidence", "low"),
            },
        )


def extract_pathways_for_protein(protein: ProteinRecord) -> list[dict[str, Any]]:
    return [
        {
            "kegg_id": protein.kegg_id,
            "name": protein.ids.get("protein_symbol", protein.kegg_id),
            "evidence": protein.semantic.get("estimated_effect", "no_effect"),
        }
    ]


def fetch_pathway_information(pathway: dict[str, Any]) -> dict[str, Any]:
    return {
        "kegg_id": pathway.get("kegg_id", ""),
        "name": pathway.get("name", ""),
        "evidence": pathway.get("evidence", "no_effect"),
        "source": "upload-profile-stream",
    }

