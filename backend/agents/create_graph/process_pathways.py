from __future__ import annotations
import asyncio
import xml.etree.ElementTree as ET
from typing import Any, Dict, List

import httpx
from fastapi import HTTPException

async def fetch_pathway_information(kegg_pathway_id: str) -> Dict[str, Any]:
    """
    Fetches the KGML XML for a given KEGG pathway ID, parses protein-protein
    interactions (PPrel), and maps directional mechanisms (inhibits, promotes/activates,
    expression, phosphorylation) alongside downstream phenotypic endpoints.
    """
    # Clean up pathway ID format (e.g., ensuring hsa04110 format)
    pathway_id = kegg_pathway_id.strip()
    kgml_url = f"https://rest.kegg.jp/get/{pathway_id}/kgml"

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(kgml_url, timeout=15.0)
            if response.status_code == 404:
                raise HTTPException(status_code=404, detail=f"Pathway {pathway_id} not found in KEGG.")
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise HTTPException(
                status_code=502, 
                detail=f"Failed to pull KGML from KEGG API: {str(exc)}"
            )

    try:
        root = ET.fromstring(response.text)
    except ET.ParseError:
        raise HTTPException(status_code=500, detail="Failed to parse the retrieved KEGG KGML structure.")

    nodes: Dict[str, Dict[str, Any]] = {}
    edges: List[Dict[str, Any]] = []

    # 1. Parse Nodes (Entries: genes, protein complexes, linked maps/phenotypes)
    for entry in root.findall("entry"):
        entry_id = entry.get("id")
        entry_type = entry.get("type")  # e.g., 'gene', 'group', 'map', 'compound'
        kegg_names = entry.get("name", "").split(" ")  # e.g., ['hsa:1029', 'hsa:1030']
        
        # Get readable graphic label
        graphics = entry.find("graphics")
        display_name = graphics.get("name") if graphics is not None else ""
        if display_name:
            # Clean up trailing punctuation often provided by KEGG labels (e.g., "TP53...")
            display_name = display_name.rstrip(".")

        # Resolve grouped items (protein complexes) if explicitly defined
        component_ids = [comp.get("id") for comp in entry.findall("component")]

        nodes[entry_id] = {
            "entry_id": entry_id,
            "type": entry_type,
            "kegg_identifiers": kegg_names,
            "display_name": display_name,
            "components": component_ids
        }

    # 2. Parse Edges (Relations: PPrel, GErel, etc.)
    for relation in root.findall("relation"):
        entry1_id = relation.get("entry1")
        entry2_id = relation.get("entry2")
        rel_type = relation.get("type")  # e.g., 'PPrel' (protein-protein), 'GErel' (gene expression)

        # Collect directional mechanical variants inside subtypes
        subtypes = relation.findall("subtype")
        mechanisms = []
        for subtype in subtypes:
            sub_name = subtype.get("name")   # e.g., 'activation', 'inhibition', 'phosphorylation'
            sub_value = subtype.get("value") # e.g., '-->', '--|', '+p'
            mechanisms.append({"mechanism": sub_name, "arrow_symbol": sub_value})

        # Generate readable lookup details for the source and target nodes
        source_node = nodes.get(entry1_id, {})
        target_node = nodes.get(entry2_id, {})

        edge_data = {
            "source_id": entry1_id,
            "source_name": source_node.get("display_name", "Unknown"),
            "source_type": source_node.get("type", "Unknown"),
            "target_id": entry2_id,
            "target_name": target_node.get("display_name", "Unknown"),
            "target_type": target_node.get("type", "Unknown"),
            "relation_type": rel_type,
            "mechanisms": mechanisms
        }
        
        edges.append(edge_data)

    return {
        "pathway_id": pathway_id,
        "pathway_title": root.get("title", "Unknown Pathway"),
        "total_nodes": len(nodes),
        "total_edges": len(edges),
        "nodes": nodes,
        "edges": edges
    }