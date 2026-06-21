"""Persist TTD drug hits to Neo4j.

Idempotent: MERGE on drugbank_id means repeat queries never duplicate nodes.
When drugbank_id is absent (some investigational drugs), we fall back to
drug_name as the merge key — still stable since names are canonical in TTD.

Graph shape written:
  (:Drug)-[:TARGETS]->(:Protein)

Drug node properties stored:
  drug_name, drugbank_id, approval_status, mechanism, ttd_source=true
"""

import backend.neo4j_http as neo4j_http
from backend.agents.ttd import DrugHit

_UPSERT_CYPHER = """
UNWIND $drugs AS d
MERGE (drug:Drug {drugbank_id: coalesce(d.drugbank_id, d.drug_name)})
ON CREATE SET
  drug.drug_name       = d.drug_name,
  drug.drugbank_id     = d.drugbank_id,
  drug.approval_status = d.approval_status,
  drug.mechanism       = d.mechanism,
  drug.ttd_source      = true
ON MATCH SET
  drug.approval_status = coalesce(d.approval_status, drug.approval_status),
  drug.mechanism       = coalesce(d.mechanism, drug.mechanism)
WITH drug, d
MATCH (p:Protein {gene_symbol: d.gene_symbol})
MERGE (drug)-[:TARGETS]->(p)
"""


def upsert_drugs(drugs: list[DrugHit]) -> None:
    """Write drug nodes and TARGETS edges to Neo4j.  Best-effort: never raises."""
    if not drugs:
        return
    try:
        neo4j_http.run_write(_UPSERT_CYPHER, {"drugs": list(drugs)})
    except Exception:
        pass  # graph write failing must never break the chat response
