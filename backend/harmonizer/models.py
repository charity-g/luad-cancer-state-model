"""Canonical identifier models for the harmonizer platform."""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class IdentifierSource(str, Enum):
    kegg_api = "kegg_api"
    uniprot_api = "uniprot_api"
    ncbi_api = "ncbi_api"
    ttd_api = "ttd_api"
    llm_inference = "llm_inference"
    input_verbatim = "input_verbatim"
    cache = "cache"


class HarmonizedGene(BaseModel):
    """Canonical gene/protein cross-reference bundle."""

    query: str                              # raw input that triggered resolution
    gene_symbol: str                        # HGNC-approved symbol (e.g. EGFR)
    kegg_gene_id: Optional[str] = None      # hsa:2065
    kegg_ko_id: Optional[str] = None        # K04361
    uniprot_ac: Optional[str] = None        # P00533
    entrez_gene_id: Optional[str] = None    # 1956
    hgnc_id: Optional[str] = None          # HGNC:3236
    ensembl_gene_id: Optional[str] = None  # ENSG00000146648
    description: Optional[str] = None

    source: IdentifierSource = IdentifierSource.kegg_api
    confidence: float = Field(ge=0.0, le=1.0, default=1.0)
    notes: list[str] = Field(default_factory=list)


class HarmonizedVariant(BaseModel):
    """Normalized variant identifier bundle."""

    query: str                              # raw mutation string
    gene_symbol: Optional[str] = None
    hgvs_cdna: Optional[str] = None        # c.2573T>G
    hgvs_protein: Optional[str] = None     # p.L858R
    genomic_coordinate: Optional[str] = None
    genome_assembly: Optional[str] = None
    transcript_id: Optional[str] = None
    refseq_protein: Optional[str] = None
    rsid: Optional[str] = None
    variant_type: Optional[str] = None     # SNV | indel | frameshift | ...
    uniprot_ac: Optional[str] = None

    source: IdentifierSource = IdentifierSource.input_verbatim
    confidence: float = Field(ge=0.0, le=1.0, default=1.0)
    notes: list[str] = Field(default_factory=list)


class HarmonizedDrug(BaseModel):
    """Canonical drug cross-reference bundle."""

    query: str                              # raw drug name input
    drug_name: str                          # normalized display name
    drugbank_id: Optional[str] = None       # DB09229
    chembl_id: Optional[str] = None         # CHEMBL1421
    pubchem_cid: Optional[str] = None
    approval_status: Optional[str] = None   # approved | clinical_trial | experimental
    mechanism: Optional[str] = None
    aliases: list[str] = Field(default_factory=list)

    source: IdentifierSource = IdentifierSource.ttd_api
    confidence: float = Field(ge=0.0, le=1.0, default=1.0)
    notes: list[str] = Field(default_factory=list)


class HarmonizedPathway(BaseModel):
    """Canonical pathway cross-reference bundle."""

    query: str                              # raw pathway query
    kegg_id: Optional[str] = None           # hsa04010
    reactome_id: Optional[str] = None       # R-HSA-1640170
    display_name: str = ""
    organism: Optional[str] = None          # hsa / mmu / ...
    category: Optional[str] = None          # signaling | metabolism | ...

    source: IdentifierSource = IdentifierSource.kegg_api
    confidence: float = Field(ge=0.0, le=1.0, default=1.0)
    notes: list[str] = Field(default_factory=list)


class HarmonizeRequest(BaseModel):
    """Batch harmonization request body."""

    genes: list[str] = Field(default_factory=list)
    variants: list[dict[str, Any]] = Field(default_factory=list)
    drugs: list[str] = Field(default_factory=list)
    pathways: list[str] = Field(default_factory=list)


class HarmonizeResponse(BaseModel):
    genes: list[HarmonizedGene] = Field(default_factory=list)
    variants: list[HarmonizedVariant] = Field(default_factory=list)
    drugs: list[HarmonizedDrug] = Field(default_factory=list)
    pathways: list[HarmonizedPathway] = Field(default_factory=list)
    cache_hits: int = 0
    api_calls: int = 0
    llm_calls: int = 0
