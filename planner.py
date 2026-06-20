"""
"""


    # "ids": [ #for harmonization
    #     {"label:": "KEGG", "description": "kegg id", "id": "hsa04010"},
    #     # label is unifrom, description llm, id is the actual id
    # ],


def extract_mutation_profiles(profiles):
    # planner should produce a list with details for each mutation
    returns list of mutations

def hydrate_mutation():
    # llm based, could be an agent on its own
    FINAL_SCHEMA: {
        "mutation_id": "id",
        "protein": "EGFR",
        "estimated_effect": "no_effect/activating/inactivating",
        all other information the llm finds necessary to justify
    }

def extract_proteins_for_mutation(mutation):
    # llm based, could be an agent on its own

def extract_pathways_for_protein(protein):
    # api call based - will need browser info maybe
    returns list of kegg pathways 

def run(profile):
    profile_id = some hash
    mutations =  extract_mutation_profiles(profile)
    
    # does mutation fulfill FINAL_SCHEMA?
    # for each mutation to produce estimated_effect on protein

    profile_pathway = [] # graph database
 
    for mutation in mutations:
        mutation = hydrate_mutation(mutation)
        # // update mutation in graph database for this profile_id
        # stream some user feedback ie update frontend

        protein = extract_proteins_for_mutation(mutation)
        # // update proteins in graph database for this profile id
        # stream some user feedback ie update frontend

        pathways = extract_pathways_for_protein(protein)
        # stream some user feedback ie update frontend

        for pathway in pathways:
            pathway_information = 
            update_pathway(pathway_information)
            # stream some user feedback ie update frontend


            # agent generate code to update the pathway into full pathway
    return {
        profile_pathway
        }