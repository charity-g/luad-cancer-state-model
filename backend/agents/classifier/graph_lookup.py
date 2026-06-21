"""Step 1–2: load unified graph and run mutation → pathway → drug lookup."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

GRAPH_PATH = Path(__file__).resolve().parent / "unified_graph.json"

ACTIVE_STATUSES = {"activated", "nsclc_enriched"}

# Variant-specific drugs — sourced from description fields in unified_graph.json.
VARIANT_DRUG_MUTATIONS: dict[str, set[str]] = {
    "sotorasib": {"KRAS G12C"},
    "adagrasib": {"KRAS G12C"},
}

# nutlin-3 only applies when TP53 is intact (not loss-of-function).
LOF_INCOMPATIBLE_DRUGS = {"nutlin-3"}


def load_graph(path: Path | str | None = None) -> dict[str, Any]:
    p = Path(path) if path else GRAPH_PATH
    data = json.loads(p.read_text())
    nodes_by_id = {n["id"]: n for n in data["nodes"]}
    drugs_by_name = {
        n["label"]: n for n in data["nodes"] if n.get("type") == "drug"
    }
    pathways_by_id = {
        n["id"]: n for n in data["nodes"] if n.get("type") == "pathway"
    }
    inhibits_by_pathway: dict[str, list[dict]] = {}
    for edge in data["edges"]:
        if edge.get("type") != "inhibits":
            continue
        inhibits_by_pathway.setdefault(edge["target"], []).append(edge)

    return {
        "raw": data,
        "nodes_by_id": nodes_by_id,
        "drugs_by_name": drugs_by_name,
        "pathways_by_id": pathways_by_id,
        "gene_index": data.get("gene_index", {}),
        "mutation_index": data.get("mutation_index", {}),
        "gene_to_drugs": data.get("gene_to_drugs", {}),
        "inhibits_by_pathway": inhibits_by_pathway,
    }


def _pathway_status(graph: dict, pathway_id: str) -> str | None:
    node = graph["pathways_by_id"].get(pathway_id)
    return node.get("status") if node else None


def _is_active_pathway(graph: dict, pathway_id: str) -> bool:
    status = _pathway_status(graph, pathway_id)
    return status in ACTIVE_STATUSES


def _drug_id_to_name(graph: dict, drug_node_id: str) -> str | None:
    node = graph["nodes_by_id"].get(drug_node_id)
    return node.get("label") if node else None


def _drug_passes_variant_filter(drug_name: str, mutation: str) -> bool:
    allowed = VARIANT_DRUG_MUTATIONS.get(drug_name)
    if allowed is not None and mutation not in allowed:
        return False
    if drug_name in LOF_INCOMPATIBLE_DRUGS and "loss" in mutation.lower():
        return False
    return True


def mutation_to_pathways(graph: dict, mutation: str) -> dict[str, Any]:
    gene = graph["mutation_index"].get(mutation)
    if not gene:
        return {"mutation": mutation, "gene": None, "pathways": [], "unknown_mutation": True}

    pathway_ids = graph["gene_index"].get(gene, [])
    pathways = []
    for pid in pathway_ids:
        node = graph["pathways_by_id"].get(pid)
        if not node:
            continue
        pathways.append(
            {
                "id": pid,
                "label": node.get("label", pid),
                "status": node.get("status"),
                "active": _is_active_pathway(graph, pid),
            }
        )
    return {"mutation": mutation, "gene": gene, "pathways": pathways, "unknown_mutation": False}


def mutation_to_drugs(graph: dict, mutation: str) -> dict[str, Any]:
    base = mutation_to_pathways(graph, mutation)
    if base["unknown_mutation"]:
        return {**base, "drugs": []}

    gene = base["gene"]
    active_pathway_ids = {p["id"] for p in base["pathways"] if p["active"]}
    seen: set[str] = set()
    drugs: list[dict[str, Any]] = []

    def add_drug(name: str, match_type: str, pathways: list[str], rank: int):
        if name in seen or not _drug_passes_variant_filter(name, mutation):
            return
        seen.add(name)
        drug_node = graph["drugs_by_name"].get(name, {})
        drugs.append(
            {
                "drug": name,
                "match_type": match_type,
                "pathways_covered": pathways,
                "rank": rank,
                "description": drug_node.get("description", ""),
            }
        )

    for drug_name in graph["gene_to_drugs"].get(gene, []):
        covered = []
        for pid in active_pathway_ids:
            for edge in graph["inhibits_by_pathway"].get(pid, []):
                if _drug_id_to_name(graph, edge["source"]) == drug_name:
                    covered.append(pid)
                    break
        add_drug(drug_name, "direct_target", covered or sorted(active_pathway_ids), rank=0)

    for pid in active_pathway_ids:
        for edge in graph["inhibits_by_pathway"].get(pid, []):
            drug_name = _drug_id_to_name(graph, edge["source"])
            if not drug_name:
                continue
            drug_node = graph["drugs_by_name"].get(drug_name, {})
            targets = set(drug_node.get("key_genes") or [])
            if gene in targets:
                continue
            add_drug(drug_name, "pathway", [pid], rank=1)

    drugs.sort(key=lambda d: (d["rank"], d["drug"]))
    return {**base, "drugs": drugs}

