from __future__ import annotations

from typing import Any

from backend.agents.create_graph.model import ProteinRecord, MutationProteinEffect



def extract_pathways_for_protein(protein: ProteinRecord) -> list[dict[str, Any]]:
    return [
        {
            "kegg_id": protein.kegg_gene_id or protein.query,
            "name": protein.gene_symbol or protein.query,
            "evidence": protein.kegg_description or protein.source or "no_effect",
        }
    ]


def fetch_pathway_information(pathway: dict[str, Any]) -> dict[str, Any]:
    return {
        "kegg_id": pathway.get("kegg_id", ""),
        "name": pathway.get("name", ""),
        "evidence": pathway.get("evidence", "no_effect"),
        "source": "upload-profile-stream",
    }

