from __future__ import annotations

import re
from typing import Optional

import httpx
from anthropic import AsyncAnthropic

from backend.agents.create_graph.model import MutationProteinEffect, ProteinResolutionError, ProteinRecord
from backend.config import ANTHROPIC_API_KEY, REASONER_MODEL


async def fetch_protein_atlas(ensemble_id: str) -> dict:
    """Fetch Human Protein Atlas data for a protein by Ensembl gene ID."""
    search_url = "https://www.proteinatlas.org/api/search_download.php"
    params = {
        "search": ensemble_id,
        "format": "json",
        "columns": "g,eg,up,scl,secl,rnats,rnatd,rnascs,di,pc,pe",
        "compress": "no",
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.get(search_url, params=params)
        r.raise_for_status()
        results = r.json()

    if not results:
        return {}

    entry = results[0]
    ensembl_id = entry.get("Ensembl")
    if not ensembl_id:
        return entry

    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.get(f"https://www.proteinatlas.org/{ensembl_id}.json")
        r.raise_for_status()
        return r.json()


async def get_kegg_id_from_protein(identifiers: dict) -> str:
    """Resolve a KEGG ID from arbitrary protein identifiers using Anthropic."""
    if not ANTHROPIC_API_KEY:
        raise ValueError("No Anthropic API key configured")

    prompt = f"""get kegg id for protein with identifiers.

identifiers:
{identifiers}

return only kegg_id"""

    client = AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
    response = await client.messages.create(
        model=REASONER_MODEL,
        max_tokens=32,
        messages=[{"role": "user", "content": prompt}],
    )

    kegg_id = response.content[0].text.strip()
    if not kegg_id:
        raise ValueError("No KEGG ID returned")
    return kegg_id


async def validate_kegg_id(kegg_id: str) -> bool:
    """Validate that a KEGG gene entry exists (e.g. hsa:1956)."""
    if not kegg_id:
        return False
    if not re.match(r"^[a-z]{3,4}:\d+$", kegg_id):
        return False

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.get(f"https://rest.kegg.jp/get/{kegg_id}")
            return r.status_code == 200 and bool(r.text.strip())
    except httpx.HTTPError:
        return False


async def _query_kegg_gene(mutation: MutationProteinEffect) -> tuple[str, str]:
    """
    Resolve a KEGG gene ID from a mutation.

    Strategy:
      1. KEGG /find/genes by gene symbol
      2. KEGG /conv/genes by UniProt AC
      3. Anthropic fallback
    """
    async with httpx.AsyncClient(timeout=15.0) as client:
        # 1. Search by gene symbol
        r = await client.get(f"https://rest.kegg.jp/find/genes/{mutation.protein}")
        if r.status_code == 200 and r.text.strip():
            first_line = r.text.strip().splitlines()[0]
            return first_line.split("\t")[0], first_line

        # 2. Fallback: UniProt → KEGG conv
        uniprot_id = mutation.identifiers.get("uniprot_ac") or mutation.identifiers.get("uniprot_id") or mutation.protein
        if uniprot_id:
            r = await client.get(f"https://rest.kegg.jp/conv/genes/uniprot:{uniprot_id}")
            if r.status_code == 200 and r.text.strip():
                first_line = r.text.strip().splitlines()[0]
                parts = first_line.split("\t")
                if len(parts) >= 2:
                    return parts[1], first_line

    # 3. Anthropic fallback
    result = (await get_kegg_id_from_protein(f"[{mutation.protein}, {mutation.identifiers}]")).strip()
    if await validate_kegg_id(result):
        return result, result

    uniprot_id = mutation.identifiers.get("uniprot_ac") or mutation.identifiers.get("uniprot_id")
    raise ProteinResolutionError(
        f"No KEGG gene entry found for symbol '{mutation.protein}' or UniProt ID '{uniprot_id}'"
    )


async def _query_kegg_ko(kegg_gene_id: str) -> Optional[str]:
    """Resolve KEGG Orthology (KO) identifier from a KEGG gene entry."""
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.get(f"https://rest.kegg.jp/get/{kegg_gene_id}")
        if r.status_code != 200:
            return None
        for line in r.text.splitlines():
            if line.startswith("ORTHOLOGY"):
                for part in line.split():
                    if part.startswith("K"):
                        return part
    except httpx.HTTPError:
        pass
    return None


async def extract_protein_for_mutation(mutation: MutationProteinEffect) -> ProteinRecord:
    """
    Map a mutation interpretation to a KEGG protein/gene record.

    Workflow: mutation → gene symbol → KEGG gene ID → optional KO ID
    Raises ProteinResolutionError if no valid mapping exists.
    """
    kegg_gene_id, raw_line = await _query_kegg_gene(mutation)
    ko_id = await _query_kegg_ko(kegg_gene_id)

    description = raw_line.split("\t", 1)[1] if "\t" in raw_line else None

    return ProteinRecord(
        query=mutation.protein,
        gene_symbol=mutation.protein,
        uniprot_id=mutation.identifiers.get("uniprot_ac") or mutation.identifiers.get("uniprot_id"),
        entrez_gene_id=mutation.identifiers.get("entrez_gene_id"),
        kegg_gene_id=kegg_gene_id,
        kegg_ko_id=ko_id,
        kegg_description=description,
        raw_response=raw_line,
    )
