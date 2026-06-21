import asyncio
import logging
from typing import Any

import anthropic

from backend.agents.create_graph.model import MutationProteinEffect, GuessMutation
from backend.config import ANTHROPIC_API_KEY, REASONER_MODEL

log = logging.getLogger(__name__)

# "you may wish to plan extra steps to retreive following information",
#         """
#         Gene symbol		Human-readable gene name
# Genomic coordinate		Exact genome location
# Genome assembly	GRCh37 / GRCh38	Defines coordinate system
# HGVS DNA notation	c.2573T>G	Standard coding DNA change
# HGVS protein notation	p.L858R	Protein-level effect
# Transcript ID	NM_005228.5	Defines transcript reference
# rsID	rs121434568	dbSNP identifier
# Variant type	SNV	Mutation category
# """

SYSTEM_PROMPT = """You are a computational biology expert specializing in variant effect prediction and protein biochemistry. You reason carefully about how genomic mutations propagate to protein-level consequences.

Your task is to analyze a mutation record and produce a structured assessment of whether and how the mutation affects its target protein. You must:
1. Extract and normalize all available identifiers from the mutation record
2. Reason about functional consequence using the evidence present
3. Return a single JSON object — no prose, no markdown fences, no explanation outside the JSON

Your output must always be valid JSON matching the schema below exactly."""

MUTATION_ANALYSIS_PROMPT = """Analyze the following mutation record and determine its likely effect on the encoded protein.

## Mutation Record
{mutation_json}

## Reasoning Protocol

Work through these steps before producing output:

**Step 1 — Identifier extraction**
From the mutation record, identify whichever of the following are present. Note which are missing.
- Gene symbol (e.g. TP53, BRCA1)
- Genomic coordinate (chr:pos or chr:start-end)
- Genome assembly (GRCh38 / GRCh37 / hg19 / hg38)
- HGVS coding DNA notation (c. prefix, e.g. c.817C>T)
- HGVS protein notation (p. prefix, e.g. p.Arg273Cys)
- Transcript ID and version (e.g. ENST00000269305.9 or NM_000546.6)
- rsID (e.g. rs28934578)
- Variant type (SNV / indel / frameshift / splice / CNV / structural)

**Step 2 — Consequence classification**
Based on the variant type, if there is rsid, and HGVS protein notation (or inferred consequence), classify the mutation using the relevant information about the rsid:
- loss_of_function: nonsense, frameshift, canonical splice site (±1/±2), large deletion
- likely_damaging: missense at conserved site, in-frame indel at functional domain
- likely_neutral: synonymous, intronic (>10bp from splice), common population variant (gnomAD AF > 1%)
- activating: known gain-of-function class (e.g. hotspot missense in kinase domain)
- uncertain: insufficient information to classify

**Step 3 — Evidence weighting**
Weight evidence in this order (highest to lowest):
1. Experimental evidence in the mutation record (functional assay, clinical classification)
2. HGVS protein notation — what amino acid change occurred and where
3. Variant type alone (frameshift → almost always loss_of_function)
4. Absence of information (treat as uncertain, not neutral)

**Step 4 — Isoform awareness**
If a transcript ID is present, anchor your reasoning to that isoform.
If no transcript is specified but multiple isoforms exist for the gene, flag this as a caveat in justification.notes.
If only a gene symbol is present with no transcript, assume canonical UniProt isoform and note this assumption.

**Step 5 — Produce output**
Return exactly this JSON schema — all fields required:


```json
{{
  "mutation_id": "<string: from input or generated as gene_hgvs>",
  "protein": "<string: UniProt AC if derivable, else gene symbol>",

  "identifiers": {{
    "hugo_symbol": "<string | null>",
    "gene_symbol": "<string | null>",
    "hgnc_id": "<string | null>",
    "uniprot_ac": "<string | null>",
    "transcript_id": "<string | null>",
    "refseq_protein": "<string | null>",
    "rsid": "<string | null>",
    "hgvs_cdna": "<string | null>",
    "hgvs_protein": "<string | null>",
    "genome_assembly": "<string | null>",
    "genomic_coordinate": "<string | null>",
    "variant_type": "<SNV|indel|frameshift|splice|CNV|structural|unknown>",
  }},

  "estimated_effect": "<loss_of_function|gain_of_function|inactivating|activating|uncertain>",

  "confidence": "<high|medium|low>",

  "justification": {{
    "reasoning": "<string: step-by-step reasoning trace — which evidence drove the classification>",
    "key_evidence": ["<string: specific field from input that most influenced decision>"],
    "missing_identifiers": ["<string: identifiers absent from input that would improve confidence>"],
    "isoform_caveat": "<string | null: note if isoform ambiguity affects interpretation>",
    "notes": ["<string: any additional flags, e.g. known hotspot, splice region proximity>"]
  }}
}}
```

## Critical constraints
- Do NOT invent identifiers. If a UniProt AC or rsID is not in the input, set it to null.
- Do NOT default estimated_effect to "no_effect" due to missing data — use "uncertain" instead.
- If variant_type is frameshift or nonsense, estimated_effect must be loss_of_function unless there is explicit contradicting evidence in the record.
- If HGVS protein notation uses p.= (synonymous) or p.? (unknown), reflect this accurately.
- Confidence is high only when HGVS protein notation AND variant type are both present and consistent.

Return only the JSON object. No other text."""


def build_mutation_prompt(mutation: dict) -> list[dict]:
    import json
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": MUTATION_ANALYSIS_PROMPT.format(
                mutation_json=json.dumps(mutation, indent=2)
            )
        }
    ]


def _hydrate_stub(mutation: dict[str, Any]) -> MutationProteinEffect:
    gene_symbol = str(mutation.get("gene_symbol") or mutation.get("gene") or mutation.get("symbol") or "")
    protein = str(mutation.get("protein") or mutation.get("uniprot_ac") or gene_symbol)
    effect = str(mutation.get("estimated_effect") or "uncertain")
    identifiers = {
        "gene_symbol": mutation.get("gene_symbol") or mutation.get("gene") or mutation.get("symbol"),
        "hgnc_id": mutation.get("hgnc_id"),
        "uniprot_ac": mutation.get("uniprot_ac"),
        "transcript_id": mutation.get("transcript_id"),
        "refseq_protein": mutation.get("refseq_protein"),
        "rsid": mutation.get("rsid"),
        "hgvs_cdna": mutation.get("hgvs_cdna"),
        "hgvs_protein": mutation.get("hgvs_protein"),
        "genome_assembly": mutation.get("genome_assembly"),
        "genomic_coordinate": mutation.get("genomic_coordinate"),
        "variant_type": mutation.get("variant_type") or "unknown",
        **mutation.get("identifiers", {}),
    }
    return MutationProteinEffect(
        mutation_id=str(
            mutation.get("mutation_id")
            or mutation.get("id")
            or f"{gene_symbol}:{mutation.get('hgvs_protein', '')}".strip(":"),
        ),
        protein=protein,
        identifiers=identifiers,
        estimated_effect=effect,
        confidence=str(mutation.get("confidence") or "low"),
        justification={
            "reasoning": "Generated without Anthropic because no API key was configured or the model call was skipped.",
            "key_evidence": [k for k in ("mutation_id", "gene_symbol", "hgvs_protein", "variant_type") if mutation.get(k) is not None],
            "missing_identifiers": [
                name
                for name, value in identifiers.items()
                if value is None
            ],
            "isoform_caveat": None,
            "notes": ["Deterministic fallback used in place of Anthropic reasoning."],
        },
    )


def _call_anthropic(prompt: list[dict[str, str]]) -> MutationProteinEffect:
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    response = client.messages.parse(
        model=REASONER_MODEL,
        max_tokens=1200,
        system=prompt[0]["content"],
        messages=prompt[1:],
        output_format=MutationProteinEffect,
    )
    parsed = getattr(response, "parsed_output", None)
    if isinstance(parsed, MutationProteinEffect):
        return parsed
    if parsed is not None:
        return MutationProteinEffect.model_validate(parsed)
    text = "".join(block.text for block in response.content if block.type == "text").strip()
    return MutationProteinEffect.model_validate_json(text)


async def hydrate_mutation(mutation: GuessMutation) -> MutationProteinEffect:
    # Run synchronous variant normalization via the harmonizer before LLM call.
    # This fills in fields the LLM prompt benefits from (hgvs, rsid, etc.) and
    # may make the LLM call unnecessary when confidence is already high.
    mutation_dict = dict(mutation)
    try:
        from backend.harmonizer import harmonizer as _harmonizer
        hv = _harmonizer.normalize_variant(mutation_dict)
        for field in ("hgvs_cdna", "hgvs_protein", "rsid", "variant_type", "genomic_coordinate"):
            val = getattr(hv, field, None)
            if val and not mutation_dict.get(field):
                mutation_dict[field] = val
    except Exception:
        pass

    raw_input = mutation_dict.get("raw") or {}

    if not ANTHROPIC_API_KEY:
        result = _hydrate_stub(mutation_dict)
        result = result.model_copy(update={"raw": raw_input})
        return await _enrich_with_gene(result)

    prompt = build_mutation_prompt(mutation_dict)

    try:
        result = await asyncio.to_thread(_call_anthropic, prompt)
        if 'uniprot_ac' in mutation_dict:
            result['identifiers']['uniprot_ac'] = mutation_dict["uniprot_ac"]
        hydrated = MutationProteinEffect.model_validate(result)
        hydrated = hydrated.model_copy(update={"raw": raw_input})
        return await _enrich_with_gene(hydrated)
    except Exception as exc:
        log.warning("hydrate_mutation LLM call failed, falling back to stub: %s", exc, exc_info=True)
        result = _hydrate_stub(mutation_dict)
        result = result.model_copy(update={"raw": raw_input})
        return await _enrich_with_gene(result)


async def _enrich_with_gene(effect: MutationProteinEffect) -> MutationProteinEffect:
    """Backfill gene cross-references (UniProt AC, KEGG IDs) via the harmonizer."""
    try:
        from backend.harmonizer import harmonizer as _harmonizer
        hg = await _harmonizer.resolve_gene(effect.protein)
        ids = dict(effect.identifiers)
        if hg.uniprot_ac and not ids.get("uniprot_ac"):
            ids["uniprot_ac"] = hg.uniprot_ac
        if hg.kegg_gene_id and not ids.get("kegg_gene_id"):
            ids["kegg_gene_id"] = hg.kegg_gene_id
        if hg.kegg_ko_id and not ids.get("kegg_ko_id"):
            ids["kegg_ko_id"] = hg.kegg_ko_id
        if hg.hgnc_id and not ids.get("hgnc_id"):
            ids["hgnc_id"] = hg.hgnc_id
        if hg.gene_symbol and not ids.get("gene_symbol"):
            ids["gene_symbol"] = hg.gene_symbol
        return effect.model_copy(update={"identifiers": ids})
    except Exception:
        return effect
