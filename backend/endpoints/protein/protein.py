from __future__ import annotations
import time
import asyncio
import csv
import hashlib
import io
import json
import httpx
from typing import Any, Dict, Optional

from fastapi import APIRouter, File, UploadFile, HTTPException, Query
import httpx

protein_router = APIRouter(prefix="/proteins", tags=["proteins"])

UNIPROT_API_URL = "https://rest.uniprot.org/uniprotkb"

async def fetch_uniprot_data(protein_id: str) -> Dict[str, Any]:
    """
    Fetches protein metadata directly from the UniProt REST API.
    """
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"{UNIPROT_API_URL}/{protein_id}",
                headers={"Accept": "application/json"}
            )
            if response.status_code == 404:
                raise HTTPException(status_code=404, detail=f"Protein {protein_id} not found in UniProt.")
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as exc:
            raise HTTPException(
                status_code=502, 
                detail=f"Error communicating with UniProt API: {str(exc)}"
            )

def extract_pathways(data: Dict[str, Any]) -> list[str]:
    """
    Extracts KEGG and Reactome pathways from the UniProt cross-references (databaseReferences).
    """
    pathways = []
    db_refs = data.get("databaseReferences", [])
    
    for ref in db_refs:
        db_type = ref.get("type")
        if db_type in ["KEGG", "Reactome"]:
            # Extract database ID, e.g., "hsa04110" or "R-HSA-1640170"
            pathway_id = ref.get("id")
            # Properties often hold contextual names
            properties = ref.get("properties", {})
            pathway_name = properties.get("PathwayName", "")
            
            display_str = f"{db_type}: {pathway_id}"
            if pathway_name:
                display_str += f" ({pathway_name})"
            pathways.append(display_str)
            
    return pathways

def extract_comment_by_type(data: Dict[str, Any], comment_type: str) -> Optional[str]:
    """
    Helper to extract explicit textual descriptions (like Function or Catalytic Activity) 
    from UniProt's comment blocks.
    """
    comments = data.get("comments", [])
    for comment in comments:
        if comment.get("commentType") == comment_type:
            texts = comment.get("texts", [])
            if texts:
                return texts[0].get("value")
    return None

# --- Routes ---

@protein_router.get("/{protein_id}")
async def get_protein_from_uniprot(protein_id: str):
    """
    Fetch mapped metadata for a specific protein accession ID from UniProt.
    """
    raw_data = await fetch_uniprot_data(protein_id)
    
    # 1. Extract Full Name
    protein_desc = raw_data.get("proteinDescription", {})
    rec_name = protein_desc.get("recommendedName", {})
    full_name = rec_name.get("fullName", {}).get("value", "Unknown Name")
    
    # 2. Extract Pathways (KEGG / Reactome)
    pathways = extract_pathways(raw_data)
    
    # 3. Extract Role (Mapped from the "FUNCTION" comment payload)
    role = extract_comment_by_type(raw_data, "FUNCTION")
    
    # 4. Extract Mechanism (Mapped from "CATALYTIC ACTIVITY" or "BIOPHYSICS" payload)
    mechanism = extract_comment_by_type(raw_data, "CATALYTIC_ACTIVITY")
    
    return {
        "proteinId": protein_id,
        "fullName": full_name,
        "pathway": pathways if pathways else "No explicit pathway cross-references found",
        "role": role if role else "No role description found",
        "mechanism": mechanism if mechanism else "No structural/catalytic mechanism listed"
    }

@protein_router.get("/graph/{protein_id}")
async def get_protein_from_graph(protein_id: str):
    """
    Placeholder endpoint for fetching protein info from your internal Knowledge Graph.
    """
    #TODO run graph query on neo4j

