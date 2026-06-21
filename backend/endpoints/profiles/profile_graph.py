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


@router.get("/profiles/{profile_id}/ppi")
def get_profile_ppi(profile_id: str):
    """Return protein-protein interaction subgraph scoped to a profile.

    Strategy: collect the gene_symbol of every Protein in the profile, then
    find all KEGG Gene→Gene edges where BOTH endpoints are in that set.
    Returns Gene nodes (which carry CRISPR/expression data) rather than Protein
    nodes so the frontend can show essentiality scores on each node.

    Also returns the Mutation→Gene effect map so the caller can colour each
    gene node by its mutation effect in this profile.
    """
    cypher = """
    MATCH (prof:Profile {profile_id: $profile_id})
          -[:HAS_MUTATION]->(m:Mutation)-[:AFFECTS]->(p:Protein)
    WITH collect(DISTINCT p.gene_symbol) AS gene_syms,
         collect({gene: p.gene_symbol,
                  effect: m.estimated_effect,
                  mutation_id: m.mutation_id}) AS mutation_effects
    MATCH (g1:Gene)-[r:ACTIVATES|INHIBITS|PHOSPHORYLATES|DEPHOSPHORYLATES
                       |BINDS|REGULATES_EXPRESSION_OF|COMPONENT_OF]->(g2:Gene)
    WHERE g1.symbol IN gene_syms AND g2.symbol IN gene_syms
    RETURN g1, r, g2, mutation_effects
    """
    try:
        result = run_read(cypher, {"profile_id": profile_id})
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))

    subgraph = result["subgraph"]
    # Attach mutation_effects to each gene node using the rows.
    effect_map: dict[str, dict] = {}
    for row in result["rows"]:
        for entry in (row.get("mutation_effects") or []):
            gene = entry.get("gene") or ""
            if gene and gene not in effect_map:
                effect_map[gene] = {
                    "estimated_effect": entry.get("effect"),
                    "mutation_id": entry.get("mutation_id"),
                }
    for node in subgraph["nodes"]:
        sym = node.get("symbol") or node.get("gene_symbol") or node.get("key") or ""
        if sym in effect_map:
            node.update(effect_map[sym])

    # Return 404 only when there are no Gene nodes at all — an empty interaction
    # set (no edges but valid genes) is still a valid response.
    gene_nodes = [n for n in subgraph["nodes"] if "Gene" in (n.get("labels") or [])]
    if not gene_nodes:
        raise HTTPException(status_code=404,
                            detail=f"No PPI data found for profile '{profile_id}'")

    return subgraph


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
