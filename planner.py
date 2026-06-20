"""
"""

FINAL_SCHEMA: {
    "mutation_id": "id",
    "protein": "EGFR",
    "estimated_effect": "no_effect/activating/inactivating",
}

    # "ids": [ #for harmonization
    #     {"label:": "KEGG", "description": "kegg id", "id": "hsa04010"},
    #     # label is unifrom, description llm, id is the actual id
    # ],


def extract_mutation_profiles(profiles):
    # planner should produce a list with details for each mutation

def run(profiles):
    mutations =  extract_mutation_profiles(profiles)
    
    # does mutation fulfill FINAL_SCHEMA?
    # for each mutation to produce estimated_effect on protein

    proteins = extract_proteins_for_mutations(mutations)
    pathways = extract_pathways_for_proteins(proteins)

    # agent generate code to update the pathway into full pathway
