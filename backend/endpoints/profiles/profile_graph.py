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


_OUTCOME_GENES = {
    # Cell cycle / proliferation
    "MYC", "CCND1", "CCND2", "CDK4", "CDK6", "CDK2", "RB1", "E2F1", "PCNA",
    # MAPK → proliferation
    "MAPK1", "MAPK3", "MAP2K1", "MAP2K2", "BRAF", "RAF1", "HRAS", "NRAS",
    # PI3K-AKT-mTOR growth
    "AKT1", "AKT2", "MTOR", "RPS6KB1", "PIK3CA", "PIK3CB",
    # Apoptosis
    "BCL2", "BCL2L1", "MCL1", "CASP3", "CASP9", "BAX", "BAD", "PARP1",
    # Tumor suppressors
    "TP53", "PTEN", "CDKN2A", "CDKN1A", "CDKN1B",
}

_OUTCOME_CATEGORY = {
    "MYC": "growth", "CCND1": "proliferation", "CCND2": "proliferation",
    "CDK4": "proliferation", "CDK6": "proliferation", "CDK2": "proliferation",
    "RB1": "proliferation", "E2F1": "proliferation",
    "MAPK1": "proliferation", "MAPK3": "proliferation",
    "MAP2K1": "proliferation", "MAP2K2": "proliferation",
    "BRAF": "proliferation", "RAF1": "proliferation",
    "AKT1": "growth", "AKT2": "growth", "MTOR": "growth",
    "PIK3CA": "growth", "PIK3CB": "growth",
    "BCL2": "survival", "BCL2L1": "survival", "MCL1": "survival",
    "CASP3": "apoptosis", "CASP9": "apoptosis", "BAX": "apoptosis",
    "TP53": "tumor_suppressor", "PTEN": "tumor_suppressor",
    "CDKN2A": "tumor_suppressor", "CDKN1A": "tumor_suppressor",
}


@router.get("/profiles/{profile_id}/ppi/cascade")
def get_profile_cascade(profile_id: str):
    """Cascade PPI from the profile's mutated proteins outward through signaling edges.

    Traverses two hops from each seed gene via ACTIVATES / INHIBITS /
    PHOSPHORYLATES / DEPHOSPHORYLATES / REGULATES_EXPRESSION_OF relationships.
    Tags each returned gene node with:
      - is_seed          True when the gene is directly mutated in this profile
      - outcome_category e.g. 'proliferation' | 'growth' | 'apoptosis' | None
    """
    # Step 1: collect seed genes + mutation effects
    seed_cypher = """
    MATCH (prof:Profile {profile_id: $profile_id})
          -[:HAS_MUTATION]->(m:Mutation)-[:AFFECTS]->(p:Protein)
    RETURN p.gene_symbol     AS gene,
           m.estimated_effect AS effect,
           m.mutation_id      AS mutation_id
    """
    try:
        seed_result = run_read(seed_cypher, {"profile_id": profile_id})
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))

    rows = seed_result.get("rows") or []
    if not rows:
        raise HTTPException(status_code=404, detail=f"Profile '{profile_id}' not found or has no mutations")

    seed_genes: set[str] = set()
    mutation_effects: dict[str, dict] = {}
    for row in rows:
        gene = row.get("gene") or ""
        if gene:
            seed_genes.add(gene)
            mutation_effects[gene] = {
                "estimated_effect": row.get("effect"),
                "mutation_id": row.get("mutation_id"),
            }

    # Step 2: two-hop cascade outward from seed genes
    cascade_cypher = """
    MATCH (g1:Gene)-[r1:ACTIVATES|INHIBITS|PHOSPHORYLATES|DEPHOSPHORYLATES|REGULATES_EXPRESSION_OF]->(g2:Gene)
    WHERE g1.symbol IN $seed_genes
    OPTIONAL MATCH (g2)-[r2:ACTIVATES|INHIBITS|PHOSPHORYLATES|DEPHOSPHORYLATES|REGULATES_EXPRESSION_OF]->(g3:Gene)
    RETURN g1, r1, g2, r2, g3
    LIMIT 300
    """
    try:
        cascade_result = run_read(cascade_cypher, {"seed_genes": list(seed_genes)})
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))

    subgraph = cascade_result["subgraph"]

    # Step 3: annotate each gene node
    for node in subgraph["nodes"]:
        sym = str(node.get("symbol") or node.get("gene_symbol") or node.get("key") or "")
        node["is_seed"] = sym in seed_genes
        node["outcome_category"] = _OUTCOME_CATEGORY.get(sym)
        node["is_outcome"] = sym in _OUTCOME_GENES
        if sym in mutation_effects:
            node.update(mutation_effects[sym])

    if not subgraph["nodes"]:
        raise HTTPException(
            status_code=404,
            detail=f"No signaling interactions found for profile '{profile_id}'"
        )

    return subgraph


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


@router.get("/profiles/{profile_id}/drugs")
def get_profile_drugs(profile_id: str):
    """Return all Drug nodes linked to proteins mutated in this profile."""
    cypher = """
    MATCH (prof:Profile {profile_id: $profile_id})
          -[:HAS_MUTATION]->(m:Mutation)-[:AFFECTS]->(p:Protein)
          <-[:TARGETS]-(d:Drug)
    RETURN d.drug_name       AS drug_name,
           d.drugbank_id     AS drugbank_id,
           d.approval_status AS approval_status,
           d.mechanism       AS mechanism,
           p.gene_symbol     AS gene_symbol,
           m.estimated_effect AS estimated_effect,
           m.mutation_id     AS mutation_id
    """
    try:
        result = run_read(cypher, {"profile_id": profile_id})
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
