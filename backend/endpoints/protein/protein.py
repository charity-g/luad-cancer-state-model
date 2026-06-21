from __future__ import annotations
import asyncio
import logging
from typing import Any, Dict, Optional

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

log = logging.getLogger(__name__)

protein_router = APIRouter(prefix="/proteins", tags=["proteins"])

UNIPROT_API_URL = "https://rest.uniprot.org/uniprotkb"
PDBE_SIFTS_URL  = "https://www.ebi.ac.uk/pdbe/api/mappings/uniprot"

# Simple in-process cache — domain annotations don't change between requests.
_domains_cache: dict[str, Any] = {}

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

# ── domain models ────────────────────────────────────────────────────────────

class DomainRange(BaseModel):
    name: str
    uniprot_start: int
    uniprot_end: int
    pdb_start: int | None = None
    pdb_end: int | None = None

class DomainsResponse(BaseModel):
    uniprot_ac: str
    pdb_id: str | None = None
    chain: str | None = None
    domains: list[DomainRange]
    sifts_available: bool = False

# ── domain helpers ────────────────────────────────────────────────────────────

def _extract_domains(uniprot_json: dict) -> list[dict]:
    """Pull Domain-type features from a UniProt entry JSON."""
    domains = []
    for feature in uniprot_json.get("features", []):
        if feature.get("type") != "Domain":
            continue
        loc = feature.get("location", {})
        start = loc.get("start", {}).get("value")
        end   = loc.get("end", {}).get("value")
        name  = feature.get("description", "Unknown domain")
        if start is not None and end is not None:
            domains.append({"name": name, "uniprot_start": int(start), "uniprot_end": int(end)})
    return domains


def _pdb_from_uniprot(uniprot_json: dict) -> tuple[str, str] | tuple[None, None]:
    """
    Extract the best PDB cross-reference directly from a UniProt entry.

    UniProt curates these links under `uniProtKBCrossReferences` with
    database='PDB'. Each entry carries a Chains property like "A/B=1-100"
    from which we pull the first chain letter. X-ray entries are preferred
    over NMR/EM; within each method the first (highest-quality) entry wins.
    Returns (pdb_id, chain) or (None, None).
    """
    refs = uniprot_json.get("uniProtKBCrossReferences", [])
    pdb_refs = [r for r in refs if r.get("database") == "PDB"]
    if not pdb_refs:
        return None, None

    def method_rank(ref: dict) -> int:
        props = {p["key"]: p["value"] for p in ref.get("properties", [])}
        m = props.get("Method", "").lower()
        if "x-ray" in m:
            return 0
        if "em" in m:
            return 1
        return 2  # NMR / other

    pdb_refs.sort(key=method_rank)
    best = pdb_refs[0]
    pdb_id = best["id"].lower()

    # Parse first chain letter from e.g. "A/B=1-100" or "A=5-300, B=5-300"
    chain = "A"
    props = {p["key"]: p["value"] for p in best.get("properties", [])}
    chains_str = props.get("Chains", "")
    if chains_str:
        first_token = chains_str.split(",")[0].strip()          # "A/B=1-100"
        chain_part  = first_token.split("=")[0].strip()         # "A/B"
        chain       = chain_part.split("/")[0].strip() or "A"   # "A"

    return pdb_id, chain


async def _sifts_offset(pdb_id: str, ac: str, client: httpx.AsyncClient) -> dict[int, int] | None:
    """
    Fetch PDBe SIFTS mapping for a PDB entry and return a dict mapping
    UniProt residue number → PDB residue number for the given UniProt AC.
    Returns None when the mapping is unavailable.
    """
    try:
        resp = await client.get(f"{PDBE_SIFTS_URL}/{pdb_id}", timeout=10)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        log.warning("SIFTS fetch failed for %s / %s: %s", pdb_id, ac, exc)
        return None

    # PDBe nests results as data[pdb_id][ac][...]["mappings"]
    entry = data.get(pdb_id.lower(), data.get(pdb_id.upper(), {}))
    ac_data = entry.get(ac, {})
    mappings: list[dict] = ac_data.get("mappings", [])

    if not mappings:
        return None

    # Build a residue-level map from the first mapping segment (covers most cases)
    # Each mapping has: unp_start, unp_end, pdb_start (struct_asym_id + residue_number)
    offset_map: dict[int, int] = {}
    for seg in mappings:
        unp_start = seg.get("unp_start")
        unp_end   = seg.get("unp_end")
        pdb_start = seg.get("start", {}).get("residue_number")
        if unp_start is None or pdb_start is None:
            continue
        shift = int(pdb_start) - int(unp_start)
        for unp_res in range(int(unp_start), int(unp_end) + 1):
            offset_map[unp_res] = unp_res + shift

    return offset_map if offset_map else None


def _apply_sifts(domains: list[dict], offset_map: dict[int, int]) -> list[DomainRange]:
    result = []
    for d in domains:
        pdb_start = offset_map.get(d["uniprot_start"])
        pdb_end   = offset_map.get(d["uniprot_end"])
        result.append(DomainRange(
            name=d["name"],
            uniprot_start=d["uniprot_start"],
            uniprot_end=d["uniprot_end"],
            pdb_start=pdb_start,
            pdb_end=pdb_end,
        ))
    return result


# ── domain endpoint ───────────────────────────────────────────────────────────

@protein_router.get("/{protein_id}/domains", response_model=DomainsResponse)
async def get_protein_domains(protein_id: str):
    """
    Returns UniProt domain annotations for a protein, with PDB structure info
    and SIFTS-mapped residue numbers for 3D viewer domain coloring.
    """
    ac = protein_id.upper()

    if ac in _domains_cache:
        return _domains_cache[ac]

    async with httpx.AsyncClient(
        headers={"Accept": "application/json"},
        follow_redirects=True,
    ) as client:
        # 1. UniProt domains
        try:
            resp = await client.get(f"{UNIPROT_API_URL}/{ac}.json", timeout=15)
            if resp.status_code == 404:
                raise HTTPException(status_code=404, detail=f"UniProt AC {ac} not found.")
            resp.raise_for_status()
            uniprot_data = resp.json()
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"UniProt fetch failed: {exc}")

        raw_domains = _extract_domains(uniprot_data)

        # 2. Best PDB structure — read directly from UniProt cross-references
        #    (always check, even when there are no annotated domains)
        pdb_id, chain = _pdb_from_uniprot(uniprot_data)

        if not raw_domains:
            result = DomainsResponse(uniprot_ac=ac, pdb_id=pdb_id, chain=chain, domains=[])
            _domains_cache[ac] = result
            return result

        if pdb_id is None:
            result = DomainsResponse(
                uniprot_ac=ac,
                domains=[DomainRange(**d) for d in raw_domains],
            )
            _domains_cache[ac] = result
            return result

        # 3. SIFTS residue mapping
        offset_map = await _sifts_offset(pdb_id, ac, client)

        if offset_map:
            domains = _apply_sifts(raw_domains, offset_map)
            sifts_available = True
        else:
            domains = [
                DomainRange(**d, pdb_start=d["uniprot_start"], pdb_end=d["uniprot_end"])
                for d in raw_domains
            ]
            sifts_available = False

    result = DomainsResponse(
        uniprot_ac=ac,
        pdb_id=pdb_id,
        chain=chain,
        domains=domains,
        sifts_available=sifts_available,
    )
    _domains_cache[ac] = result
    return result


# ── existing routes ───────────────────────────────────────────────────────────

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

