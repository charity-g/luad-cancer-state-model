from backend.agents.create_graph.model import MutationProteinEffect
from typing import Any 

def hydrate_mutation(mutation: dict[str, Any]) -> MutationProteinEffect:
    return MutationProteinEffect(
        mutation_id=str(mutation.get("mutation_id", "")),
        protein=str(mutation.get("protein", "")),
        estimated_effect=str(mutation.get("estimated_effect", "no_effect")),
        justification={
            "raw": mutation.get("raw", {}),
            "notes": mutation.get("notes", []),
        },
    )