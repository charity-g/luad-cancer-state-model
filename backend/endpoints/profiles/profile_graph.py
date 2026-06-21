from fastapi import APIRouter, HTTPException
from backend.neo4j_http import run_read

router = APIRouter()


@router.get("/profiles/{profile_id}/graph")
def get_profile_graph(profile_id: str):
    """Return all Mutation → Protein → Pathway nodes and edges for a profile."""
    cypher = """
    MATCH (prof:Profile {profile_id: $profile_id})
    OPTIONAL MATCH (prof)-[:HAS_MUTATION]->(m:Mutation)
    OPTIONAL MATCH (m)-[a:AFFECTS]->(p:Protein)
    OPTIONAL MATCH (p)-[i:INVOLVED_IN]->(pw:Pathway)
    RETURN prof, m, a, p, i, pw
    """
    try:
        result = run_read(cypher, {"profile_id": profile_id})
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))

    subgraph = result["subgraph"]
    if not subgraph["nodes"]:
        raise HTTPException(status_code=404, detail=f"Profile '{profile_id}' not found")

    return subgraph
