"""Identifier harmonization platform.

Import the singleton:

    from backend.harmonizer import harmonizer

    gene  = await harmonizer.resolve_gene("EGFR")
    drug  = await harmonizer.resolve_drug("osimertinib")
    path  = await harmonizer.resolve_pathway("hsa04010")
    var   = harmonizer.normalize_variant(raw_mutation_dict)
"""

from backend.harmonizer.service import harmonizer
from backend.harmonizer.models import (
    HarmonizedGene,
    HarmonizedVariant,
    HarmonizedDrug,
    HarmonizedPathway,
    HarmonizeRequest,
    HarmonizeResponse,
)

__all__ = [
    "harmonizer",
    "HarmonizedGene",
    "HarmonizedVariant",
    "HarmonizedDrug",
    "HarmonizedPathway",
    "HarmonizeRequest",
    "HarmonizeResponse",
]
