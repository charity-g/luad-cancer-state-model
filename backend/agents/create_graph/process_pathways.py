from __future__ import annotations

from typing import Any

from backend.agents.create_graph.model import ProteinRecord


def extract_protein_for_mutation(mutation: dict[str, Any]) -> ProteinRecord:
    protein_symbol = str(mutation.get("protein", "")).strip()
    protein_symbol = protein_symbol or "EGFR"
    return ProteinRecord(
        kegg_id=f"hsa:{protein_symbol}",
        ids={
            "mutation_id": str(mutation.get("mutation_id", "")),
            "protein_symbol": protein_symbol,
        },
        semantic={
            "estimated_effect": mutation.get("estimated_effect", "no_effect"),
            "source_mutation": mutation,
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

