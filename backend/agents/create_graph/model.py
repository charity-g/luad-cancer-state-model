
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
	"""LLM-produced mutation-to-protein interpretation.

	Required fields:
	- mutation_id: stable mutation identifier
	- protein: target protein symbol, for example EGFR
	- estimated_effect: one of no_effect, activating, inactivating

	The model stays permissive so the LLM can attach any additional evidence,
	explanations, or provenance needed to justify the call.
	"""

	mutation_id: str
	protein: str
	estimated_effect: str
	justification: dict[str, Any] = Field(default_factory=dict)

	class Config:
		extra = "allow"

