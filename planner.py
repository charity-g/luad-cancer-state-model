"""
"""

FINAL_SCHEMA: {
    "mutation_id": "id",
    "protein": "EGFR",
    "estimated affect": "no_effect/activating/inactivating",
}

    # "ids": [ #for harmonization
    #     {"label:": "KEGG", "description": "kegg id", "id": "hsa04010"},
    #     # label is unifrom, description llm, id is the actual id
    # ],


def extract_mutation_profiles(profiles):
    # planner should plan how to extract mutation profiles


def run(profiles):
    mutations =  extract_mutation_profiles(profiles)
    
    # does mutation fulfill FINAL_SCHEMA?
    
    proteins = extract_proteins_for_mutations(mutations)
    extract_pathways_for_proteins(proteins)

