
from typing import Any

from pydantic import BaseModel, Field


# "ids": [ #for harmonization
#     {"label:": "KEGG", "description": "kegg id", "id": "hsa04010"},
#     # label is unifrom, description llm, id is the actual id
# ],


class ProteinRecord(BaseModel):
	"""Flexible protein payload for graph creation.

	The only required identifier is ``kegg_id``. Any additional identifiers can
	be stored in ``ids``, and free-form semantic facts can be stored in
	``semantic``. Extra fields are also allowed so the model can absorb new
	annotations without schema churn.
	"""

	kegg_id: str
	ids: dict[str, str] = Field(default_factory=dict)
	semantic: dict[str, Any] = Field(default_factory=dict)

	class Config:
		extra = "allow"


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
	estimated_effect: str
	confidence: str
	justification: dict[str, Any] = Field(default_factory=dict)

	class Config:
		extra = "allow"

