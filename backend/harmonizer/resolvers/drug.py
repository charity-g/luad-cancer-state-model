"""Drug identifier resolver.

Normalizes drug names and resolves cross-database IDs.

Strategy:
  1. Cache hit (normalized name → HarmonizedDrug)
  2. Fuzzy name normalization (case, common aliases, salt forms)
  3. DrugBank alias table (hard-coded common oncology drugs)
  4. LLM inference for unknown names

No TTD calls here — TTD integration stays in backend/agents/ttd.py.
The harmonizer augments TTD results with canonical IDs.
"""

from __future__ import annotations

import re

from backend.harmonizer.models import HarmonizedDrug, IdentifierSource

# Canonical name → DrugBank ID + aliases for common LUAD/oncology drugs
_DRUG_REGISTRY: dict[str, dict] = {
    "erlotinib":    {"drugbank_id": "DB00530", "aliases": ["tarceva", "OSI-774"]},
    "gefitinib":    {"drugbank_id": "DB00317", "aliases": ["iressa", "ZD1839"]},
    "afatinib":     {"drugbank_id": "DB08916", "aliases": ["gilotrif", "BIBW-2992"]},
    "osimertinib":  {"drugbank_id": "DB11963", "aliases": ["tagrisso", "AZD9291", "mereletinib"]},
    "dacomitinib":  {"drugbank_id": "DB11979", "aliases": ["vizimpro", "PF-00299804"]},
    "sotorasib":    {"drugbank_id": "DB15661", "aliases": ["lumakras", "AMG-510"]},
    "adagrasib":    {"drugbank_id": "DB16045", "aliases": ["krazati", "MRTX-849"]},
    "crizotinib":   {"drugbank_id": "DB08865", "aliases": ["xalkori", "PF-02341066"]},
    "alectinib":    {"drugbank_id": "DB11942", "aliases": ["alecensa", "CH5424802"]},
    "brigatinib":   {"drugbank_id": "DB11741", "aliases": ["alunbrig", "AP26113"]},
    "lorlatinib":   {"drugbank_id": "DB12658", "aliases": ["lorbrena", "PF-06463922"]},
    "cetuximab":    {"drugbank_id": "DB00002", "aliases": ["erbitux", "C225"]},
    "bevacizumab":  {"drugbank_id": "DB00112", "aliases": ["avastin"]},
    "pembrolizumab":{"drugbank_id": "DB09037", "aliases": ["keytruda", "MK-3475"]},
    "nivolumab":    {"drugbank_id": "DB09035", "aliases": ["opdivo", "BMS-936558"]},
    "atezolizumab": {"drugbank_id": "DB11595", "aliases": ["tecentriq", "MPDL3280A"]},
    "durvalumab":   {"drugbank_id": "DB11901", "aliases": ["imfinzi", "MEDI4736"]},
    "pemetrexed":   {"drugbank_id": "DB00642", "aliases": ["alimta", "LY231514"]},
    "cisplatin":    {"drugbank_id": "DB00515", "aliases": ["platinol", "CDDP"]},
    "carboplatin":  {"drugbank_id": "DB00958", "aliases": ["paraplatin", "CBDCA"]},
    "docetaxel":    {"drugbank_id": "DB01248", "aliases": ["taxotere"]},
    "paclitaxel":   {"drugbank_id": "DB01229", "aliases": ["taxol"]},
    "vemurafenib":  {"drugbank_id": "DB08881", "aliases": ["zelboraf", "PLX4032"]},
    "trametinib":   {"drugbank_id": "DB08911", "aliases": ["mekinist", "GSK1120212"]},
    "nutlin-3":     {"drugbank_id": "DB12465", "aliases": ["nutlin3", "RG7112"]},
    "imatinib":     {"drugbank_id": "DB00619", "aliases": ["gleevec", "STI571"]},
}

# Build reverse alias lookup once
_ALIAS_TO_CANONICAL: dict[str, str] = {}
for _canonical, _meta in _DRUG_REGISTRY.items():
    _ALIAS_TO_CANONICAL[_canonical] = _canonical
    for _alias in _meta.get("aliases", []):
        _ALIAS_TO_CANONICAL[_alias.lower()] = _canonical


def _normalize_name(name: str) -> str:
    """Lowercase, strip salt forms and extra whitespace."""
    name = name.lower().strip()
    name = re.sub(r"\s+(hydrochloride|hcl|mesylate|tosylate|sodium|potassium)$", "", name)
    name = re.sub(r"[^a-z0-9\-]", "", name)
    return name


def lookup_drug(name: str) -> HarmonizedDrug:
    """
    Synchronously resolve a drug name to a HarmonizedDrug.

    Returns a low-confidence record when the name is unknown.
    """
    normalized = _normalize_name(name)
    canonical = _ALIAS_TO_CANONICAL.get(normalized)

    if canonical and canonical in _DRUG_REGISTRY:
        meta = _DRUG_REGISTRY[canonical]
        return HarmonizedDrug(
            query=name,
            drug_name=canonical,
            drugbank_id=meta.get("drugbank_id"),
            aliases=meta.get("aliases", []),
            source=IdentifierSource.input_verbatim,
            confidence=1.0,
        )

    # Unknown drug — return minimal record
    return HarmonizedDrug(
        query=name,
        drug_name=normalized or name,
        source=IdentifierSource.input_verbatim,
        confidence=0.3,
        notes=[f"Drug {name!r} not in local registry; DrugBank ID unknown"],
    )


async def resolve_drug(name: str) -> HarmonizedDrug:
    """
    Async drug resolution with LLM fallback for unknown names.
    """
    result = lookup_drug(name)
    if result.confidence >= 0.8:
        return result

    # LLM fallback
    try:
        from anthropic import AsyncAnthropic
        from backend.config import ANTHROPIC_API_KEY, REASONER_MODEL

        if not ANTHROPIC_API_KEY:
            return result

        client = AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
        resp = await client.messages.create(
            model=REASONER_MODEL,
            max_tokens=80,
            messages=[{
                "role": "user",
                "content": (
                    f"For the oncology drug '{name}', return JSON with keys: "
                    "canonical_name, drugbank_id (or null), aliases (list). No prose."
                ),
            }],
        )
        import json
        text = resp.content[0].text.strip().lstrip("```json").rstrip("```").strip()
        data = json.loads(text)
        return HarmonizedDrug(
            query=name,
            drug_name=data.get("canonical_name") or result.drug_name,
            drugbank_id=data.get("drugbank_id"),
            aliases=data.get("aliases") or [],
            source=IdentifierSource.llm_inference,
            confidence=0.75,
            notes=["Resolved via LLM inference"],
        )
    except Exception:
        return result
