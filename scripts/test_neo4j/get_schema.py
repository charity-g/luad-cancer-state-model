from neo4j import GraphDatabase
from neo4j_graphrag.schema import get_structured_schema, get_schema

# 1. Initialize connection using your API credentials
URI = "bolt://localhost:7687"  # Replace with your Neo4j Aura or local URI
AUTH = ("neo4j", "your-api-password")

driver = GraphDatabase.driver(URI, auth=AUTH)

try:
    # Option A: Get a beautifully formatted text summary (perfect for prompt building)
    text_schema = get_schema(driver, database="neo4j")
    print("=== TEXT SCHEMA FOR LLM PROMPT ===")
    print(text_schema)
    
    print("\n" + "="*40 + "\n")

    # Option B: Get a programmatic python dict mapping nodes, rels, and data types
    structured_schema = get_structured_schema(driver, database="neo4j")
    print("=== STRUCTURED PYTHON DICT ===")
    import pprint
    pprint.pprint(structured_schema)

finally:
    driver.close()