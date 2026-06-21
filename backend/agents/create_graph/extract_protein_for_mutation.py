from __future__ import annotations

import httpx
from typing import Optional
import requests
from backend.agents.create_graph.model import MutationProteinEffect, ProteinResolutionError, ProteinRecord

from backend.config import ANTHROPIC_API_KEY, REASONER_MODEL



async def fetch_protein_atlas(ensemble_id: str) -> dict:
    """
    Fetch Human Protein Atlas data for a protein by UniProt AC.
    HPA's API keys on Ensembl gene ID, so we resolve via search first.
    """
    # Step 1: search by UniProt AC to get the Ensembl ID
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

    entry = results[0]  # first hit
    ensembl_id = entry.get("Ensembl")

    if not ensembl_id:
        return entry  # return what we have

    # Step 2: fetch the full entry by Ensembl ID for complete data
    full_url = f"https://www.proteinatlas.org/{ensembl_id}.json"
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.get(full_url)
        r.raise_for_status()
        return r.json()


from anthropic import Anthropic




def get_kegg_id_from_protein(identifiers: dict) -> str:
    """
    Resolve a KEGG ID from arbitrary protein identifiers using Anthropic.

    Example identifiers:
        {
            "uniprot_id": "P00533",
            "gene_symbol": "EGFR"
        }

    Returns:
        str: KEGG gene identifier (e.g. "hsa:1956")

    Raises:
        ValueError: if no KEGG ID could be extracted
    """
    if not ANTHROPIC_API_KEY:
        raise ValueError("No anthropic key")
    prompt = f"""
    get kegg id for protein with identifiers.

    identifiers:
    {identifiers}

    return only kegg_id
    """

    client = Anthropic(api_key=ANTHROPIC_API_KEY)
    
    response = client.messages.create(
        model=REASONER_MODEL,
        max_tokens=32,
        messages=[
            {
                "role": "user",
                "content": prompt,
            }
        ],
    )

    kegg_id = response.content[0].text.strip()

    if not kegg_id:
        raise ValueError("No KEGG ID returned")

    return kegg_id


def validate_kegg_id(kegg_id: str) -> bool:
    """
    Validate that a KEGG gene entry exists.

    Example valid IDs:
        hsa:1956
        mmu:13649
    """

    if not kegg_id:
        return False

    # basic KEGG format validation
    if not re.match(r"^[a-z]{3,4}:\d+$", kegg_id):
        return False

    url = f"https://rest.kegg.jp/get/{kegg_id}"

    try:
        response = requests.get(url, timeout=15)

        return response.status_code == 200 and bool(response.text.strip())

    except requests.RequestException:
        return False

def _query_kegg_gene(mutation: MutationProteinEffect) -> tuple[str, str]:
    """
    Query KEGG genes endpoint. If finding by symbol fails, falls back to UniProt conversion.

    Returns:
        (kegg_gene_id, raw_line)
    """
    # 1. Try finding by symbol first
    url = f"https://rest.kegg.jp/find/genes/{mutation.protein}"
    response = requests.get(url, timeout=15)

    if response.status_code == 200 and response.text.strip():
        text = response.text.strip()
        first_line = text.splitlines()[0]
        kegg_gene_id = first_line.split("\t")[0]
        return kegg_gene_id, first_line

    # 2. Fallback: Try converting from UniProt ID if symbol lookup failed
    uniprot_id = mutation.identifiers.get("uniprot_ac") or mutation.identifiers.get("uniprot_id")
    
    if uniprot_id:
        url = f"https://rest.kegg.jp/conv/genes/uniprot:{uniprot_id}"
        response = requests.get(url, timeout=15)
        
        if response.status_code == 200 and response.text.strip():
            text = response.text.strip()
            first_line = text.splitlines()[0]
            
            # example response: up:P00533   hsa:1956
            # We split by tab to get the KEGG ID on the right side
            parts = first_line.split("\t")
            if len(parts) >= 2:
                kegg_gene_id = parts[1]
                return kegg_gene_id, first_line

    # 3. Try anthropic : 
    result = get_kegg_id_from_protein(f"[{mutation.protein}, {mutation.identifiers}]")
    
    result = result.strip()
    if validate_kegg_id(result):
        kegg_id = result

    else:
        # 4. If all attempts failed, raise error
        raise ProteinResolutionError(
            f"No KEGG gene entry found for symbol "
            f"'{mutation.protein}' or UniProt ID '{uniprot_id}'"
        )


def _query_kegg_ko(kegg_gene_id: str) -> Optional[str]:
    """
    Resolve KEGG Orthology (KO) identifier from KEGG gene entry.
    """
    url = f"https://rest.kegg.jp/get/{kegg_gene_id}"
    response = requests.get(url, timeout=15)

    if response.status_code != 200:
        return None

    text = response.text

    for line in text.splitlines():
        if line.startswith("ORTHOLOGY"):
            # example:
            # ORTHOLOGY  K04361  epidermal growth factor receptor
            parts = line.split()
            for part in parts:
                if part.startswith("K"):
                    return part

    return None


def extract_protein_for_mutation(
    mutation: MutationProteinEffect,
) -> ProteinRecord:
    """
    Map a mutation interpretation object to a KEGG protein/gene record.

    Workflow:
        mutation -> gene/protein symbol -> KEGG gene -> optional KO mapping

    Raises:
        ProteinResolutionError if no valid mapping exists.
    """
    # Pass the full mutation object to handle both .protein and .identifiers inside
    kegg_gene_id, raw_line = _query_kegg_gene(mutation)
    ko_id = _query_kegg_ko(kegg_gene_id)

    # parse description
    description = None
    if "\t" in raw_line:
        description = raw_line.split("\t", 1)[1]

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