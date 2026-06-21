from fastapi import APIRouter, HTTPException
from backend.neo4j_http import run_read

router = APIRouter()


@router.get("/profiles")
def list_profiles():
    """Return all stored profiles with mutation counts, newest first."""
    cypher = """
    MATCH (prof:Profile)
    OPTIONAL MATCH (prof)-[:HAS_MUTATION]->(m:Mutation)
    RETURN prof.profile_id   AS profile_id,
           prof.created_at   AS created_at,
           count(m)          AS mutation_count
    ORDER BY prof.created_at DESC
    """
    try:
        result = run_read(cypher)
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    return result["rows"]


@router.get("/profiles/{profile_id}/graph")
def get_profile_graph(profile_id: str):
    """Return the full profile subgraph:
    Profile → Mutation → Protein → Pathway ← Protein (other pathway members).
    The second protein hop (p2) gives pathway context proteins beyond the
    directly-mutated ones, so the frontend can show what else each pathway
    contains up to terminal result nodes.
    """
    cypher = """
    MATCH (prof:Profile {profile_id: $profile_id})
    OPTIONAL MATCH (prof)-[:HAS_MUTATION]->(m:Mutation)
    OPTIONAL MATCH (m)-[a:AFFECTS]->(p:Protein)
    OPTIONAL MATCH (p)-[i:INVOLVED_IN]->(pw:Pathway)
    OPTIONAL MATCH (pw)<-[i2:INVOLVED_IN]-(p2:Protein)
    RETURN prof, m, a, p, i, pw, p2, i2
    """
    try:
        result = run_read(cypher, {"profile_id": profile_id})
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))

    subgraph = result["subgraph"]
    if not subgraph["nodes"]:
        raise HTTPException(status_code=404, detail=f"Profile '{profile_id}' not found")

    return subgraph
