"""Pathway identifier resolver.

Accepts: KEGG pathway ID (hsa04010), display name, or Reactome ID.
Returns HarmonizedPathway with canonical IDs and display name.
"""

from __future__ import annotations

import re
from typing import Optional

import httpx

from backend.harmonizer.models import HarmonizedPathway, IdentifierSource

_KEGG_PATHWAY_RE = re.compile(r"^([a-z]{2,4})(\d{5})$")
_REACTOME_RE = re.compile(r"^R-[A-Z]{2,4}-\d+$")
_TIMEOUT = 15.0


def _parse_kegg_pathway_id(s: str) -> Optional[tuple[str, str]]:
    """Return (organism, number) if s is a KEGG pathway ID like hsa04010."""
    m = _KEGG_PATHWAY_RE.match(s.strip().lower())
    if m:
        return m.group(1), m.group(2)
    return None


async def _fetch_kegg_pathway_name(kegg_id: str) -> Optional[str]:
    """GET the KEGG pathway flat-file and return the NAME field."""
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            r = await client.get(f"https://rest.kegg.jp/get/path:{kegg_id}")
        if r.status_code != 200:
            return None
        for line in r.text.splitlines():
            if line.startswith("NAME"):
                name = line[4:].strip()
                # Strip trailing " - Homo sapiens (human)" annotation
                name = re.sub(r"\s*-\s*[A-Z][a-z].*$", "", name).strip()
                return name
    except httpx.HTTPError:
        pass
    return None


async def _kegg_find_pathway(query: str) -> Optional[str]:
    """Search KEGG for a pathway by name; return first hsa pathway ID."""
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            r = await client.get(f"https://rest.kegg.jp/find/pathway/{query}")
        if r.status_code != 200 or not r.text.strip():
            return None
        for line in r.text.strip().splitlines():
            pid = line.split("\t")[0].replace("path:", "")
            if pid.startswith("hsa"):
                return pid
    except httpx.HTTPError:
        pass
    return None


async def resolve_pathway(query: str) -> HarmonizedPathway:
    """
    Resolve a pathway identifier or name to a HarmonizedPathway.
    """
    query = query.strip()

    # Already a KEGG pathway ID
    parsed = _parse_kegg_pathway_id(query)
    if parsed:
        organism, _ = parsed
        display_name = await _fetch_kegg_pathway_name(query) or query
        return HarmonizedPathway(
            query=query,
            kegg_id=query,
            display_name=display_name,
            organism=organism,
            source=IdentifierSource.kegg_api,
            confidence=1.0,
        )

    # Already a Reactome ID
    if _REACTOME_RE.match(query):
        return HarmonizedPathway(
            query=query,
            reactome_id=query,
            display_name=query,
            source=IdentifierSource.input_verbatim,
            confidence=0.9,
        )

    # Free-text search via KEGG
    kegg_id = await _kegg_find_pathway(query)
    if kegg_id:
        display_name = await _fetch_kegg_pathway_name(kegg_id) or query
        parsed2 = _parse_kegg_pathway_id(kegg_id)
        organism = parsed2[0] if parsed2 else None
        return HarmonizedPathway(
            query=query,
            kegg_id=kegg_id,
            display_name=display_name,
            organism=organism,
            source=IdentifierSource.kegg_api,
            confidence=0.85,
            notes=["Resolved by KEGG keyword search"],
        )

    return HarmonizedPathway(
        query=query,
        display_name=query,
        source=IdentifierSource.input_verbatim,
        confidence=0.2,
        notes=[f"Could not resolve pathway {query!r} via KEGG"],
    )
