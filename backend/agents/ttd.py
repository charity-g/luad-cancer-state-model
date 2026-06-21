"""Therapeutic Target Database (TTD) client.

Two entry points:
  is_drug_question(text) -> bool         -- regex gate; call before fetch
  fetch_target_drugs(gene, protein_change) -> list[DrugHit]

Cache-first: if Drug nodes already exist in Neo4j for the given protein,
the API call is skipped and the cached rows are returned.  On a fresh hit the
caller is expected to persist via ttd_writer.upsert_drugs().
"""

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from typing import TypedDict

import backend.neo4j_http as neo4j_http
from backend.config import TTD_API_KEY, TTD_BASE_URL

# ---------------------------------------------------------------------------
# Drug-question detection
# ---------------------------------------------------------------------------

_DRUG_RE = re.compile(
    r"\b(drug|drugs|inhibitor|inhibit|compound|therapeutic|therapy|therapies|"
    r"approved|clinical|treat|treatment|target(?:ed|ing)?|medication|"
    r"chemotherapy|kinase inhibitor|sensitiv|resist|repurpos)\b",
    re.I,
)


def is_drug_question(text: str) -> bool:
    return bool(_DRUG_RE.search(text))


# ---------------------------------------------------------------------------
# Shared response schema
# ---------------------------------------------------------------------------

class DrugHit(TypedDict):
    drug_name: str
    drugbank_id: str
    approval_status: str
    mechanism: str
    gene_symbol: str   # the protein this hit targets (filled in by caller)


# ---------------------------------------------------------------------------
# Cache check — skip the API if we already have Drug→Protein in Neo4j
# ---------------------------------------------------------------------------

def _cached_drugs(gene_symbol: str) -> list[DrugHit]:
    """Return Drug nodes already stored in the graph for this protein."""
    try:
        result = neo4j_http.run_read(
            """
            MATCH (d:Drug)-[:TARGETS]->(p:Protein {gene_symbol: $gene})
            RETURN d.drug_name        AS drug_name,
                   d.drugbank_id      AS drugbank_id,
                   d.approval_status  AS approval_status,
                   d.mechanism        AS mechanism
            """,
            {"gene": gene_symbol},
        )
        return [
            DrugHit(
                drug_name=row.get("drug_name") or "",
                drugbank_id=row.get("drugbank_id") or "",
                approval_status=row.get("approval_status") or "",
                mechanism=row.get("mechanism") or "",
                gene_symbol=gene_symbol,
            )
            for row in result["rows"]
        ]
    except Exception:
        return []


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

_TIMEOUT = 10  # seconds per TTD request


def _get(path: str, params: dict | None = None) -> dict:
    url = TTD_BASE_URL.rstrip("/") + path
    if params:
        url += "?" + urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {TTD_API_KEY}"})
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
        return json.loads(resp.read())


def _post(path: str, body: dict) -> dict:
    url = TTD_BASE_URL.rstrip("/") + path
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Authorization": f"Bearer {TTD_API_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
        return json.loads(resp.read())


# ---------------------------------------------------------------------------
# Public fetch
# ---------------------------------------------------------------------------

def _harmonize_drug_hits(hits: list[DrugHit]) -> list[DrugHit]:
    """Enrich DrugHit records with canonical names and DrugBank IDs from the harmonizer."""
    from backend.harmonizer.resolvers.drug import lookup_drug
    enriched = []
    for hit in hits:
        hd = lookup_drug(hit["drug_name"])
        enriched.append(DrugHit(
            drug_name=hd.drug_name if hd.confidence >= 0.8 else hit["drug_name"],
            drugbank_id=hd.drugbank_id or hit["drugbank_id"],
            approval_status=hit["approval_status"],
            mechanism=hit["mechanism"],
            gene_symbol=hit["gene_symbol"],
        ))
    return enriched


def fetch_target_drugs(gene_symbol: str, protein_change: str | None = None) -> list[DrugHit]:
    """Return drugs for a protein target (or specific variant).

    Order of precedence:
      1. Neo4j cache — returns immediately if nodes already exist.
      2. POST /variants/query — used when protein_change is provided.
      3. GET /targets/{gene}/drugs — general protein lookup.

    Returns [] when TTD_API_KEY is unset or the API call fails.
    """
    cached = _cached_drugs(gene_symbol)
    if cached:
        return _harmonize_drug_hits(cached)

    if not TTD_API_KEY:
        return []

    try:
        if protein_change:
            payload = _post("/variants/query", {
                "gene_symbol": gene_symbol,
                "protein_change": protein_change,
            })
            raw_drugs = payload.get("drugs") or []
            hits = [
                DrugHit(
                    drug_name=d.get("drug_name") or "",
                    drugbank_id=d.get("drugbank_id") or "",
                    approval_status=d.get("evidence_level") or "",
                    mechanism=d.get("mechanism") or "",
                    gene_symbol=gene_symbol,
                )
                for d in raw_drugs
            ]
        else:
            payload = _get(f"/targets/{urllib.parse.quote(gene_symbol)}/drugs",
                           {"approved_only": False, "include_trials": True})
            raw_drugs = payload.get("drugs") or []
            hits = [
                DrugHit(
                    drug_name=d.get("drug_name") or "",
                    drugbank_id=d.get("drugbank_id") or "",
                    approval_status=d.get("approval_status") or "",
                    mechanism=d.get("mechanism") or "",
                    gene_symbol=gene_symbol,
                )
                for d in raw_drugs
            ]
        return _harmonize_drug_hits(hits)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, Exception):
        # TTD unavailable or bad response — degrade gracefully, never crash the agent.
        return []
