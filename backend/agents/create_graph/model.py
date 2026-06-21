
from typing import Any, Optional

from pydantic import BaseModel, Field


# "ids": [ #for harmonization
#     {"label:": "KEGG", "description": "kegg id", "id": "hsa04010"},
#     # label is unifrom, description llm, id is the actual id
# ],


class ProteinRecord(BaseModel):
    """Resolved protein/gene annotation record."""

    query: str

    # normalized identifiers
    gene_symbol: Optional[str] = None
    uniprot_id: Optional[str] = None
    entrez_gene_id: Optional[str] = None

    # KEGG annotations
    kegg_gene_id: Optional[str] = None
    kegg_ko_id: Optional[str] = None
    kegg_description: Optional[str] = None

    # provenance/debugging
    source: str = "KEGG REST API"
    raw_response: Optional[str] = None


class ProteinResolutionError(Exception):
    """Raised when a mutation cannot be mapped to a protein."""



class MutationProteinEffect(BaseModel):
	"""Mutation-to-protein interpretation payload.

	Required fields:
	- mutation_id: stable mutation identifier
	- protein: UniProt AC if derivable, else gene symbol
	- identifiers: normalized evidence fields extracted from the input record
	- estimated_effect: functional interpretation of the mutation
	- confidence: confidence in the interpretation
	- justification: reasoning and evidence summary

	The model stays permissive so the LLM or deterministic hydrators can attach
	additional evidence, provenance, or debugging fields without schema churn.
	"""

	mutation_id: str
	protein: str
	identifiers: dict[str, Any] = Field(default_factory=dict)
	# one of  "estimated_effect": "<loss_of_function|gain_of_function|inactivating|activating|uncertain>"
	estimated_effect: str
	confidence: str
	justification: dict[str, Any] = Field(default_factory=dict)

	class Config:
		extra = "allow"

class GuessMutation(BaseModel):	
	mutation_id: str
	protein: str
	
	class Config:
		extra = "allow"
