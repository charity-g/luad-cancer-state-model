"""Variant identifier normalizer.

Takes a raw mutation dict (from CSV parse or user input) and produces a
HarmonizedVariant with canonical HGVS, cross-references, and confidence.

Strategy:
  1. Extract known fields verbatim (hgvs_protein, rsid, etc.)
  2. Attempt lightweight pattern normalization (p. prefix, c. prefix)
  3. Ask Claude to fill gaps when key fields are missing and API key is set

No external API calls are made for pure normalization — this keeps variant
resolution fast and offline-capable.  LLM is only called when confidence
would otherwise be low.
"""

from __future__ import annotations

import re
from typing import Any

from backend.harmonizer.models import HarmonizedVariant, IdentifierSource

_HGVS_CDNA_RE = re.compile(r"c\.[^\s,;]+")
_HGVS_PROT_RE = re.compile(r"p\.[A-Za-z*?0-9_\[\]()]+")
_RSID_RE = re.compile(r"rs\d+", re.I)
_ENST_RE = re.compile(r"ENST\d+(\.\d+)?", re.I)
_REFSEQ_NM_RE = re.compile(r"NM_\d+(\.\d+)?", re.I)
_REFSEQ_NP_RE = re.compile(r"NP_\d+(\.\d+)?", re.I)
_UNIPROT_RE = re.compile(
    r"^([OPQ][0-9][A-Z0-9]{3}[0-9]|[A-NR-Z][0-9](?:[A-Z][A-Z0-9]{2}[0-9]){1,2})$"
)

_VARIANT_TYPE_HINTS = {
    "frameshift": "frameshift",
    "nonsense": "nonsense",
    "splice": "splice",
    "deletion": "deletion",
    "insertion": "insertion",
    "indel": "indel",
    "snv": "SNV",
    "snp": "SNV",
    "substitution": "SNV",
    "cnv": "CNV",
    "amplification": "CNV",
    "structural": "structural",
}


def _first_match(pattern: re.Pattern, *sources: str) -> str | None:
    for s in sources:
        if not s:
            continue
        m = pattern.search(str(s))
        if m:
            return m.group(0)
    return None


def _infer_variant_type(raw: dict[str, Any]) -> str | None:
    """Heuristic variant type inference from raw field values."""
    combined = " ".join(str(v) for v in raw.values() if v).lower()
    for keyword, vtype in _VARIANT_TYPE_HINTS.items():
        if keyword in combined:
            return vtype
    # HGVS frameshift indicator
    hgvs_p = str(raw.get("hgvs_protein") or raw.get("ProteinChange") or "")
    if "fs" in hgvs_p or "Ter" in hgvs_p or "*" in hgvs_p:
        return "frameshift"
    return None


def _normalize_hgvs_protein(s: str | None) -> str | None:
    """Ensure p. prefix and standard amino-acid three-letter codes."""
    if not s:
        return None
    s = s.strip()
    if not s.startswith("p.") and re.match(r"[A-Z][a-z]{2}\d+", s):
        s = "p." + s
    return s or None


def normalize_variant(raw: dict[str, Any]) -> HarmonizedVariant:
    """
    Synchronously normalize a raw mutation dict to a HarmonizedVariant.

    Accepts field names from both DepMap CSVs and the internal hydrated schema.
    """
    # Gene symbol — try common aliases
    gene_symbol = (
        raw.get("gene_symbol")
        or raw.get("hugo_symbol")
        or raw.get("HugoSymbol")
        or raw.get("gene")
        or raw.get("protein")  # often gene symbol in this codebase
    )

    # HGVS fields
    hgvs_cdna = (
        raw.get("hgvs_cdna")
        or raw.get("DNAChange")
        or _first_match(_HGVS_CDNA_RE, raw.get("raw_variant", ""), raw.get("notes", ""))
    )
    hgvs_protein = _normalize_hgvs_protein(
        raw.get("hgvs_protein")
        or raw.get("ProteinChange")
        or _first_match(_HGVS_PROT_RE, raw.get("raw_variant", ""), raw.get("notes", ""))
    )

    # Transcript / RefSeq
    transcript_id = (
        raw.get("transcript_id")
        or raw.get("EnsemblFeatureID")
        or _first_match(_ENST_RE, raw.get("VepHGVSc", ""))
        or _first_match(_REFSEQ_NM_RE, raw.get("transcript_id", ""))
    )
    refseq_protein = (
        raw.get("refseq_protein")
        or raw.get("VepENSP")
        or _first_match(_REFSEQ_NP_RE, raw.get("refseq_protein", ""))
    )

    # rsID
    rsid = raw.get("rsid") or raw.get("DbsnpRsID") or _first_match(_RSID_RE, raw.get("rsid", ""))

    # Genomic coordinate
    chrom = raw.get("Chrom") or raw.get("chrom")
    pos = raw.get("Pos") or raw.get("pos")
    genomic_coordinate = (
        raw.get("genomic_coordinate")
        or (f"{chrom}:{pos}" if chrom and pos else None)
    )
    genome_assembly = raw.get("genome_assembly") or raw.get("GenomeChange", "")
    if genome_assembly and "GRCh" not in genome_assembly and "hg" not in genome_assembly:
        genome_assembly = None  # not an assembly string

    # UniProt AC
    uniprot_ac = raw.get("uniprot_ac") or raw.get("uniprot_id")
    if uniprot_ac and not _UNIPROT_RE.match(str(uniprot_ac)):
        uniprot_ac = None

    # Variant type
    variant_type = (
        raw.get("variant_type")
        or raw.get("VariantType")
        or _infer_variant_type(raw)
        or "unknown"
    )

    # Confidence: higher when we have both HGVS fields
    confidence = 1.0 if (hgvs_cdna and hgvs_protein) else (0.7 if hgvs_protein else 0.4)

    notes: list[str] = []
    missing = [
        name for name, val in [
            ("hgvs_cdna", hgvs_cdna),
            ("hgvs_protein", hgvs_protein),
            ("rsid", rsid),
            ("transcript_id", transcript_id),
        ]
        if not val
    ]
    if missing:
        notes.append(f"Missing identifiers: {', '.join(missing)}")

    return HarmonizedVariant(
        query=str(raw.get("mutation_id") or raw.get("protein") or ""),
        gene_symbol=str(gene_symbol) if gene_symbol else None,
        hgvs_cdna=hgvs_cdna,
        hgvs_protein=hgvs_protein,
        genomic_coordinate=genomic_coordinate,
        genome_assembly=genome_assembly,
        transcript_id=transcript_id,
        refseq_protein=refseq_protein,
        rsid=rsid,
        variant_type=variant_type,
        uniprot_ac=uniprot_ac,
        source=IdentifierSource.input_verbatim,
        confidence=confidence,
        notes=notes,
    )


async def enrich_variant_with_llm(variant: HarmonizedVariant, raw: dict[str, Any]) -> HarmonizedVariant:
    """
    Use Claude to fill missing identifiers when confidence is low.
    Returns the same variant enriched in-place (new object).
    """
    if variant.confidence >= 0.7:
        return variant

    try:
        import json
        from anthropic import AsyncAnthropic
        from backend.config import ANTHROPIC_API_KEY, REASONER_MODEL

        if not ANTHROPIC_API_KEY:
            return variant

        client = AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
        resp = await client.messages.create(
            model=REASONER_MODEL,
            max_tokens=256,
            messages=[{
                "role": "user",
                "content": (
                    "Extract biological identifiers from this mutation record. "
                    "Return JSON with keys: gene_symbol, hgvs_cdna, hgvs_protein, "
                    "rsid, transcript_id, variant_type, genome_assembly. "
                    "Use null for missing fields. No prose.\n\n"
                    f"{json.dumps(raw, indent=2)}"
                ),
            }],
        )
        text = resp.content[0].text.strip()
        # Strip markdown fences if present
        if text.startswith("```"):
            text = "\n".join(text.splitlines()[1:])
        if text.endswith("```"):
            text = "\n".join(text.splitlines()[:-1])

        filled = json.loads(text)
        updates = {k: v for k, v in filled.items() if v and not getattr(variant, k, None)}
        enriched = variant.model_copy(update={
            **updates,
            "source": IdentifierSource.llm_inference,
            "confidence": min(variant.confidence + 0.2, 0.9),
            "notes": variant.notes + ["Enriched via LLM identifier extraction"],
        })
        return enriched
    except Exception:
        return variant
