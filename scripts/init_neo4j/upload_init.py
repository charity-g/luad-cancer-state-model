from neo4j import GraphDatabase
import json

URI = "bolt://localhost:7687"  # adjust your Neo4j connection
AUTH = ("neo4j", "password")   # your credentials

def load_pathways_to_neo4j():
    driver = GraphDatabase.driver(URI, auth=AUTH)
    
    with open("lung_cancer_pathways_graph.json") as f:
        data = json.load(f)
    
    with driver.session() as session:
        # Create nodes
        for node in data["nodes"]:
            session.run("""
                CREATE (p:Pathway {
                    id: $id,
                    label: $label,
                    kegg_id: $kegg_id,
                    status: $status,
                    q_value: $q_value,
                    deg_count: $deg_count
                })
            """, **node)
        
        # Create relationships
        for edge in data["edges"]:
            session.run("""
                MATCH (source:Pathway {id: $source})
                MATCH (target:Pathway {id: $target})
                CREATE (source)-[r:PATHWAY_INTERACTION {
                    type: $type,
                    shared_genes: $shared_genes,
                    description: $description
                }]->(target)
            """, **edge)
    
    driver.close()

if __name__ == "__main__":
    load_pathways_to_neo4j()