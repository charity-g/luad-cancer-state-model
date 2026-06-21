"""
"""

from backend.agents.create_graph.model import MutationProteinEffect, ProteinRecord


def extract_mutation_profiles(profiles):
    # planner should produce a list with details for each mutation
    returns list of mutations

def hydrate_mutation(mutation: any) -> MutationProteinEffect:
    # llm based, could be an agent on its own
    
    # does mutation fulfill FINAL_SCHEMA?
    # for each mutation to produce estimated_effect on protein

    return {} # ensure MutationProteinEffect is validated

def extract_protein_for_mutation(mutation) -> ProteinRecord:
    # llm based, could be an agent on its own
    # vector db 

    return {
        # kegg_id: kegg_id_for_protien, #MANDATORY
        # any other ids
        # any information semantic information
    } # ensure it returns ProteinRecord type. otherwise it must retry to raise error

def extract_pathways_for_protein(protein: ProteinRecord):
    kegg_id  = protein['kegg_id']
    # api call based - will need browser info maybe
    # https://www.kegg.jp/dbget-bin/www_bget?hsa:2065

    return [] # list of kegg pathways 

def update_pathway():
    # generate graph database code to update pathway

def run(profile):
    profile_id = some hash
    mutations =  extract_mutation_profiles(profile)
    
    profile_pathway = [] # graph database
 
    for mutation in mutations:
        hydrated_mutation = hydrate_mutation(mutation)
        # // update mutation in graph database for this profile_id
        # stream some user feedback ie update frontend

        protein = extract_protein_for_mutation(mutation)
        # // update proteins in graph database for this profile id
        # stream some user feedback ie update frontend

        pathways = extract_pathways_for_protein(protein)
        # stream some user feedback ie update frontend

        for pathway in pathways:
            pathway_information = api
            update_pathway(pathway_information)
            # stream some user feedback ie update frontend


            # agent generate code to update the pathway into full pathway
    return {
        profile_pathway
        }