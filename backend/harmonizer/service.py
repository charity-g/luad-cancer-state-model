"""Central identifier harmonization service.

Single entry point for all identifier resolution in the pipeline.
Uses the shared TTL cache to avoid redundant API calls across requests.

Usage
-----
from backend.harmonizer.service import harmonizer

gene = await harmonizer.resolve_gene("EGFR")
variant = harmonizer.normalize_variant(raw_mutation_dict)
drug = await harmonizer.resolve_drug("osimertinib")
pathway = await harmonizer.resolve_pathway("hsa04010")
"""

from __future__ import annotations

import asyncio
from typing import Any

from backend.harmonizer.cache import harmonizer_cache
from backend.harmonizer.models import (
    HarmonizedDrug,
    HarmonizedGene,
    HarmonizedPathway,
    HarmonizedVariant,
    HarmonizeRequest,
    HarmonizeResponse,
    IdentifierSource,
)
from backend.harmonizer.resolvers.drug import resolve_drug
from backend.harmonizer.resolvers.gene import resolve_gene
from backend.harmonizer.resolvers.pathway import resolve_pathway
from backend.harmonizer.resolvers.variant import enrich_variant_with_llm, normalize_variant


class IdentifierHarmonizer:
    """
    Stateless facade over all identifier resolvers.

    All public methods are safe to call concurrently — the underlying cache
    is protected against duplicate in-flight requests by keying on the query
    string before the await.
    """

    # ------------------------------------------------------------------
    # Gene / protein
    # ------------------------------------------------------------------

    async def resolve_gene(self, query: str) -> HarmonizedGene:
        """Resolve any gene symbol, UniProt AC, or KEGG ID to a canonical record."""
        key = f"gene:{query}"
        cached = harmonizer_cache.get(key)
        if cached is not None:
            return HarmonizedGene.model_validate({**cached, "source": IdentifierSource.cache})

        result = await resolve_gene(query)
        harmonizer_cache.set(key, result.model_dump())
        return result

    async def resolve_genes(self, queries: list[str]) -> list[HarmonizedGene]:
        """Batch-resolve genes concurrently."""
        return list(await asyncio.gather(*[self.resolve_gene(q) for q in queries]))

    # ------------------------------------------------------------------
    # Variant
    # ------------------------------------------------------------------

    def normalize_variant(self, raw: dict[str, Any]) -> HarmonizedVariant:
        """Fast synchronous variant normalization — no network calls."""
        return normalize_variant(raw)

    async def resolve_variant(self, raw: dict[str, Any]) -> HarmonizedVariant:
        """Normalize variant and optionally enrich low-confidence records via LLM."""
        key = f"variant:{raw.get('mutation_id') or str(sorted(raw.items()))}"
        cached = harmonizer_cache.get(key)
        if cached is not None:
            return HarmonizedVariant.model_validate(cached)

        variant = normalize_variant(raw)
        variant = await enrich_variant_with_llm(variant, raw)
        harmonizer_cache.set(key, variant.model_dump())
        return variant

    # ------------------------------------------------------------------
    # Drug
    # ------------------------------------------------------------------

    async def resolve_drug(self, name: str) -> HarmonizedDrug:
        """Normalize a drug name and resolve cross-database IDs."""
        key = f"drug:{name.lower().strip()}"
        cached = harmonizer_cache.get(key)
        if cached is not None:
            return HarmonizedDrug.model_validate({**cached, "source": IdentifierSource.cache})

        result = await resolve_drug(name)
        harmonizer_cache.set(key, result.model_dump())
        return result

    async def resolve_drugs(self, names: list[str]) -> list[HarmonizedDrug]:
        return list(await asyncio.gather(*[self.resolve_drug(n) for n in names]))

    # ------------------------------------------------------------------
    # Pathway
    # ------------------------------------------------------------------

    async def resolve_pathway(self, query: str) -> HarmonizedPathway:
        """Resolve a KEGG ID, Reactome ID, or pathway name."""
        key = f"pathway:{query}"
        cached = harmonizer_cache.get(key)
        if cached is not None:
            return HarmonizedPathway.model_validate({**cached, "source": IdentifierSource.cache})

        result = await resolve_pathway(query)
        harmonizer_cache.set(key, result.model_dump())
        return result

    async def resolve_pathways(self, queries: list[str]) -> list[HarmonizedPathway]:
        return list(await asyncio.gather(*[self.resolve_pathway(q) for q in queries]))

    # ------------------------------------------------------------------
    # Batch
    # ------------------------------------------------------------------

    async def harmonize_batch(self, req: HarmonizeRequest) -> HarmonizeResponse:
        """Process a mixed-type batch request concurrently."""
        genes_fut = asyncio.gather(*[self.resolve_gene(g) for g in req.genes])
        variants_fut = asyncio.gather(*[self.resolve_variant(v) for v in req.variants])
        drugs_fut = asyncio.gather(*[self.resolve_drug(d) for d in req.drugs])
        pathways_fut = asyncio.gather(*[self.resolve_pathway(p) for p in req.pathways])

        genes, variants, drugs, pathways = await asyncio.gather(
            genes_fut, variants_fut, drugs_fut, pathways_fut
        )

        cache_hits = sum(
            1 for r in [*genes, *variants, *drugs, *pathways]
            if r.source == IdentifierSource.cache
        )
        llm_calls = sum(
            1 for r in [*genes, *variants, *drugs, *pathways]
            if r.source == IdentifierSource.llm_inference
        )
        api_calls = sum(
            1 for r in [*genes, *variants, *drugs, *pathways]
            if r.source in (IdentifierSource.kegg_api, IdentifierSource.uniprot_api, IdentifierSource.ttd_api)
        )

        return HarmonizeResponse(
            genes=list(genes),
            variants=list(variants),
            drugs=list(drugs),
            pathways=list(pathways),
            cache_hits=cache_hits,
            api_calls=api_calls,
            llm_calls=llm_calls,
        )

    # ------------------------------------------------------------------
    # Cache management
    # ------------------------------------------------------------------

    def cache_stats(self) -> dict:
        return {"size": harmonizer_cache.size}

    def clear_cache(self) -> None:
        harmonizer_cache.clear()


# Module-level singleton — import and use directly
harmonizer = IdentifierHarmonizer()
