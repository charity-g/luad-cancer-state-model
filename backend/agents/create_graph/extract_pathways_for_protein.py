"""
KEGG pathway extraction for a protein.

The right endpoint is /link — not /get.
  GET https://rest.kegg.jp/link/pathway/{kegg_gene_id}

Response is TSV, one row per pathway the gene belongs to:
  hsa:2065\tpath:hsa04010
  hsa:2065\tpath:hsa04012
  ...

ProteinRecord is assumed to have at minimum a `kegg_id` field (e.g. "hsa:2065").
Adjust the attribute name below if your model differs.
"""

import httpx
import logging
from backend.agents.create_graph.model import ProteinRecord

logger = logging.getLogger(__name__)

KEGG_REST_BASE = "https://rest.kegg.jp"


class KEGGError(Exception):
    """Raised when the KEGG API returns an unexpected response."""


def _parse_link_response(text: str) -> list[str]:
    """
    Parse TSV response from /link/pathway/<gene>.

    Each line:  hsa:2065\tpath:hsa04010
    We return the raw pathway IDs: ["hsa04010", ...]
    stripping the "path:" prefix so callers get bare IDs
    consistent with how pathway IDs are stored elsewhere.
    """
    pathway_ids: list[str] = []

    for line in text.strip().splitlines():
        if not line:
            continue

        parts = line.split("\t")
        if len(parts) != 2:
            logger.warning("Unexpected KEGG link line format: %r", line)
            continue

        # parts[1] is e.g. "path:hsa04010"
        raw_pathway = parts[1].strip()
        pathway_id = raw_pathway.removeprefix("path:")
        pathway_ids.append(pathway_id)

    return pathway_ids


def extract_pathways_for_protein(protein: "ProteinRecord") -> list[dict[str, str]]:
    """
    Return KEGG pathway IDs for a protein, given its KEGG gene ID.

    Args:
        protein: ProteinRecord with a populated `kegg_id` (e.g. "hsa:2065").

    Returns:
        List of pathway IDs e.g. ["hsa04010", "hsa04012", "hsa04014"].
        Returns [] if the protein has no KEGG ID or no pathways are found.

    Raises:
        KEGGError: On non-200 HTTP responses or malformed payloads.
    """
    kegg_id: str | None = getattr(protein, "kegg_gene_id", None)

    if not kegg_id:
        logger.warning(
            "ProteinRecord %r has no kegg_id — skipping pathway extraction",
            getattr(protein, "uniprot_id", repr(protein)),
        )
        return []

    url = f"{KEGG_REST_BASE}/link/pathway/{kegg_id}"
    logger.debug("Fetching KEGG pathways: GET %s", url)

    try:
        response = httpx.get(url, timeout=10.0)
    except httpx.RequestError as exc:
        raise KEGGError(f"Network error fetching KEGG pathways for {kegg_id}") from exc

    if response.status_code == 404:
        # Gene exists in KEGG but has no pathway associations — valid empty result
        logger.info("No KEGG pathways found for %s (404)", kegg_id)
        return []

    if response.status_code != 200:
        raise KEGGError(
            f"KEGG API returned {response.status_code} for {kegg_id}: {response.text[:200]}"
        )

    if not response.text.strip():
        # 200 with empty body also means no pathway associations
        logger.info("Empty KEGG pathway response for %s", kegg_id)
        return []

    pathway_ids = _parse_link_response(response.text)
    logger.debug("Found %d pathways for %s: %s", len(pathway_ids), kegg_id, pathway_ids)
    return [
        {
            "kegg_id": pathway_id,
            "name": pathway_id,
            "evidence": protein.kegg_description or "KEGG pathway link",
        }
        for pathway_id in pathway_ids
    ]


# ---------------------------------------------------------------------------
# Async variant — drop-in for async callers
# ---------------------------------------------------------------------------

async def extract_pathways_for_protein_async(protein: ProteinRecord) -> list[dict[str, str]]:
    """Async version of extract_pathways_for_protein."""
    kegg_id: str | None = getattr(protein, "kegg_gene_id", None)

    if not kegg_id:
        logger.warning(
            "ProteinRecord %r has no kegg_id — skipping pathway extraction",
            getattr(protein, "uniprot_id", repr(protein)),
        )
        return []

    url = f"{KEGG_REST_BASE}/link/pathway/{kegg_id}"
    logger.debug("Fetching KEGG pathways: GET %s", url)

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url)
    except httpx.RequestError as exc:
        raise KEGGError(f"Network error fetching KEGG pathways for {kegg_id}") from exc

    if response.status_code == 404:
        logger.info("No KEGG pathways found for %s (404)", kegg_id)
        return []

    if response.status_code != 200:
        raise KEGGError(
            f"KEGG API returned {response.status_code} for {kegg_id}: {response.text[:200]}"
        )

    if not response.text.strip():
        logger.info("Empty KEGG pathway response for %s", kegg_id)
        return []

    pathway_ids = _parse_link_response(response.text)
    logger.debug("Found %d pathways for %s: %s", len(pathway_ids), kegg_id, pathway_ids)
    return [
        {
            "kegg_id": pathway_id,
            "name": pathway_id,
            "evidence": protein.kegg_description or "KEGG pathway link",
        }
        for pathway_id in pathway_ids
    ]
