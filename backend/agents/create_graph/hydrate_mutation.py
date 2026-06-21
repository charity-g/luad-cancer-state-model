from backend.agents.create_graph.model import MutationProteinEffect
from typing import Any 


#TODO

async def hydrate_mutation(mutation: dict[str, Any]) -> MutationProteinEffect:
    enriched = dict(mutation)
    
    llm_plan = (
        "given this mutation, determine the best plan of how to figure out if this mutation will affect the protein"
    )

    llm_prompt = (
        "given this mutation, find if it matches identifiers"
        """
        Gene symbol	EGFR	Human-readable gene name
Genomic coordinate	chr7:55259515 T>G	Exact genome location
Genome assembly	GRCh37 / GRCh38	Defines coordinate system
HGVS DNA notation	c.2573T>G	Standard coding DNA change
HGVS protein notation	p.L858R	Protein-level effect
Transcript ID	NM_005228.5	Defines transcript reference
rsID	rs121434568	dbSNP identifier
Variant type	SNV	Mutation category
"""
    ) 
    


    # Step 3: pass enriched context to your LLM reasoning step
    return await llm_reason(mutation, external)

def hydrate_mutation(mutation: dict[str, Any]) -> MutationProteinEffect:
    
    return MutationProteinEffect(
        mutation_id=str(mutation.get("mutation_id", "")),
        protein=str(mutation.get("protein", "")),
        estimated_effect=str(mutation.get("estimated_effect", "no_effect")),
        justification={
            "raw": mutation.get("raw", {}),
            "notes": mutation.get("notes", []),
        },
    ),