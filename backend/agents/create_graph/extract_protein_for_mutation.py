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
        print('uniprot_id for query kegg', uniprot_id)
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


_UNIPROT_RE = re.compile(
    r'^([OPQ][0-9][A-Z0-9]{3}[0-9]|[A-NR-Z][0-9](?:[A-Z][A-Z0-9]{2}[0-9]){1,2})$'
)

def _looks_like_uniprot(s: str) -> bool:
    return bool(_UNIPROT_RE.match(s.strip()))


async def _query_kegg_entry(kegg_gene_id: str) -> dict:
    """
    Fetch a KEGG gene flat-file entry and extract:
      ko_id       — KEGG Orthology ID (K-number)
      gene_symbol — canonical gene symbol (first NAME token)
      description — one-line gene definition (DEFINITION field)
    """
    result: dict = {"ko_id": None, "gene_symbol": None, "description": None}
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.get(f"https://rest.kegg.jp/get/{kegg_gene_id}")
        if r.status_code != 200:
            return result
        for line in r.text.splitlines():
            if line.startswith("NAME"):
                # "NAME        SETD2, HIF1, HYPB, KMT3A..."  — first token is canonical
                name_part = line[4:].strip()
                result["gene_symbol"] = name_part.split(",")[0].strip()
            elif line.startswith("DEFINITION"):
                result["description"] = line[10:].strip()
            elif line.startswith("ORTHOLOGY"):
                for part in line.split():
                    if part.startswith("K") and part[1:].isdigit():
                        result["ko_id"] = part
                        break
    except httpx.HTTPError:
        pass
    return result


async def extract_protein_for_mutation(mutation: MutationProteinEffect) -> ProteinRecord:
    """
    Map a mutation interpretation to a KEGG protein/gene record.

    Workflow: mutation → KEGG gene ID → full KEGG entry (symbol, description, KO)
    Raises ProteinResolutionError if no valid mapping exists.
    """
    kegg_gene_id, raw_line = await _query_kegg_gene(mutation)
    entry = await _query_kegg_entry(kegg_gene_id)

    # Resolve UniProt AC in priority order:
    #   1. Hydrated identifiers (LLM path)
    #   2. KEGG conv response line  e.g. "up:Q96T58\thsa:23013"
    #   3. mutation.protein itself when it looks like a UniProt AC (stub path)
    uniprot_id = (
        mutation.identifiers.get("uniprot_ac")
        or mutation.identifiers.get("uniprot_id")
    )
    if not uniprot_id:
        first_col = raw_line.split("\t")[0]
        if first_col.startswith("up:"):
            uniprot_id = first_col[3:]
        elif _looks_like_uniprot(mutation.protein):
            uniprot_id = mutation.protein

    return ProteinRecord(
        query=mutation.protein,
        gene_symbol=entry["gene_symbol"] or mutation.protein,
        uniprot_id=uniprot_id or None,
        entrez_gene_id=mutation.identifiers.get("entrez_gene_id"),
        kegg_gene_id=kegg_gene_id,
        kegg_ko_id=entry["ko_id"],
        kegg_description=entry["description"] or kegg_gene_id,
        raw_response=raw_line,
    )
