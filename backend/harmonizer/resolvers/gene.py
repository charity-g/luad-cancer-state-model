"""Gene/protein identifier resolver.

Resolution order:
  1. Cache hit
  2. KEGG /find/genes by symbol
  3. KEGG /conv/genes by UniProt AC (when input looks like an AC)
  4. KEGG /get for full entry (symbol, KO, description)
  5. LLM inference (Claude) when all API paths fail

Returns HarmonizedGene with all available cross-references.
"""

from __future__ import annotations

import re
from typing import Optional

import httpx

from backend.harmonizer.models import HarmonizedGene, IdentifierSource

_UNIPROT_RE = re.compile(
    r"^([OPQ][0-9][A-Z0-9]{3}[0-9]|[A-NR-Z][0-9](?:[A-Z][A-Z0-9]{2}[0-9]){1,2})$"
)
_KEGG_GENE_RE = re.compile(r"^[a-z]{2,4}:\d+$")

_TIMEOUT = 15.0


def _looks_like_uniprot(s: str) -> bool:
    return bool(_UNIPROT_RE.match(s.strip()))


def _looks_like_kegg_gene(s: str) -> bool:
    return bool(_KEGG_GENE_RE.match(s.strip()))


async def _kegg_find_by_symbol(symbol: str, client: httpx.AsyncClient) -> Optional[str]:
    """Return first KEGG gene ID matching a human gene symbol."""
    r = await client.get(f"https://rest.kegg.jp/find/genes/{symbol}")
    if r.status_code != 200 or not r.text.strip():
        return None
    # Filter for human (hsa:) entries first; fall back to first result
    lines = r.text.strip().splitlines()
    for line in lines:
        kegg_id = line.split("\t")[0]
        if kegg_id.startswith("hsa:"):
            return kegg_id
    return lines[0].split("\t")[0]


async def _kegg_conv_uniprot(uniprot_ac: str, client: httpx.AsyncClient) -> Optional[str]:
    """Convert UniProt AC → KEGG gene ID via /conv endpoint."""
    r = await client.get(f"https://rest.kegg.jp/conv/genes/uniprot:{uniprot_ac}")
    if r.status_code != 200 or not r.text.strip():
        return None
    first_line = r.text.strip().splitlines()[0]
    parts = first_line.split("\t")
    if len(parts) >= 2:
        return parts[1]
    return None


async def _kegg_get_entry(kegg_gene_id: str, client: httpx.AsyncClient) -> dict:
    """Fetch a KEGG flat-file entry and extract core fields."""
    result: dict = {
        "gene_symbol": None,
        "ko_id": None,
        "description": None,
        "uniprot_ac": None,
    }
    r = await client.get(f"https://rest.kegg.jp/get/{kegg_gene_id}")
    if r.status_code != 200:
        return result
    for line in r.text.splitlines():
        if line.startswith("NAME") and result["gene_symbol"] is None:
            result["gene_symbol"] = line[4:].strip().split(",")[0].strip()
        elif line.startswith("DEFINITION") and result["description"] is None:
            result["description"] = line[10:].strip()
        elif line.startswith("ORTHOLOGY") and result["ko_id"] is None:
            for part in line.split():
                if part.startswith("K") and part[1:].isdigit():
                    result["ko_id"] = part
                    break
        elif "UniProt:" in line and result["uniprot_ac"] is None:
            # "DBLINKS     UniProt: P00533"
            m = re.search(r"UniProt:\s*(\S+)", line)
            if m:
                result["uniprot_ac"] = m.group(1)
    return result


async def _llm_resolve_gene(query: str) -> Optional[str]:
    """Ask Claude for the KEGG gene ID when all API paths fail."""
    try:
        from anthropic import AsyncAnthropic
        from backend.config import ANTHROPIC_API_KEY, REASONER_MODEL

        if not ANTHROPIC_API_KEY:
            return None

        client = AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
        resp = await client.messages.create(
            model=REASONER_MODEL,
            max_tokens=24,
            messages=[{
                "role": "user",
                "content": (
                    f"Return only the KEGG human gene ID (format hsa:NNNNN) for: {query}. "
                    "No explanation."
                ),
            }],
        )
        candidate = resp.content[0].text.strip()
        if _looks_like_kegg_gene(candidate):
            return candidate
    except Exception:
        pass
    return None


async def resolve_gene(query: str) -> HarmonizedGene:
    """
    Resolve any gene/protein identifier to a HarmonizedGene.

    `query` may be a gene symbol (EGFR), UniProt AC (P00533),
    KEGG gene ID (hsa:2065), or Entrez ID.
    """
    notes: list[str] = []
    source = IdentifierSource.kegg_api

    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        kegg_gene_id: Optional[str] = None

        # Fast path: already a KEGG ID
        if _looks_like_kegg_gene(query):
            kegg_gene_id = query
        elif _looks_like_uniprot(query):
            kegg_gene_id = await _kegg_conv_uniprot(query, client)
            if not kegg_gene_id:
                notes.append(f"UniProt→KEGG conv failed for {query}")
        else:
            # Treat as gene symbol
            kegg_gene_id = await _kegg_find_by_symbol(query, client)
            if not kegg_gene_id:
                notes.append(f"KEGG find failed for symbol {query}")

        if not kegg_gene_id:
            # LLM fallback
            kegg_gene_id = await _llm_resolve_gene(query)
            if kegg_gene_id:
                source = IdentifierSource.llm_inference
                notes.append("KEGG ID resolved via LLM inference")
            else:
                # Return minimal record from input
                return HarmonizedGene(
                    query=query,
                    gene_symbol=query,
                    source=IdentifierSource.input_verbatim,
                    confidence=0.2,
                    notes=[f"Could not resolve {query!r} via KEGG or LLM"],
                )

        entry = await _kegg_get_entry(kegg_gene_id, client)

    uniprot_ac: Optional[str] = None
    if _looks_like_uniprot(query):
        uniprot_ac = query
    elif entry.get("uniprot_ac"):
        uniprot_ac = entry["uniprot_ac"]

    gene_symbol = entry.get("gene_symbol") or query

    return HarmonizedGene(
        query=query,
        gene_symbol=gene_symbol,
        kegg_gene_id=kegg_gene_id,
        kegg_ko_id=entry.get("ko_id"),
        uniprot_ac=uniprot_ac,
        description=entry.get("description"),
        source=source,
        confidence=1.0 if source == IdentifierSource.kegg_api else 0.75,
        notes=notes,
    )
