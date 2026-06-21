"""
Neo4j drug + protein target graph updater.

Uses the Neo4j HTTP Query API (port 443 / HTTPS) — the same transport as the
backend — so it works on networks that block the Bolt port (7687).

Adds / updates:
  - ProteinTarget nodes  (TTD / DrugBank)
  - Drug nodes           (DrugBank / TTD)
  - Mutation nodes       (OncoKB / ClinVar)
  - TARGETS edges        Drug  → ProteinTarget
  - TREATS  edges        Drug  → Mutation
  - AFFECTS edges        Mutation → ProteinTarget
  - PARTICIPATES_IN edges ProteinTarget → Pathway  (bridges therapeutic → KEGG layer)

Identifier harmonization:
  ProteinTarget.gene_symbol = Gene.symbol = Mutation.gene_symbol
  This is the join key between the therapeutic layer (this script) and the
  KEGG/DepMap genomic layer loaded by the main pipeline.

Environment variables required:
  NEO4J_URI       https://xxxxx.databases.neo4j.io   (HTTPS, NOT neo4j+s://)
  NEO4J_USERNAME
  NEO4J_PASSWORD

Example:
    export NEO4J_URI="https://xxxxx.databases.neo4j.io"
    export NEO4J_USERNAME="neo4j"
    export NEO4J_PASSWORD="password"
    python upload_http.py

Requirements:
    pip install python-dotenv   (no neo4j driver needed)
"""

from __future__ import annotations

import base64
import http.client
import json
import os
import time
from typing import Any
from urllib.parse import urlparse

from dotenv import load_dotenv


load_dotenv()


# -----------------------------------------------------------------------------
# ENV
# -----------------------------------------------------------------------------

NEO4J_URI      = os.getenv("NEO4J_URI", "")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")

if not NEO4J_URI:
    raise ValueError("Missing NEO4J_URI — set it to https://xxxxx.databases.neo4j.io")
if not NEO4J_USERNAME:
    raise ValueError("Missing NEO4J_USERNAME")
if not NEO4J_PASSWORD:
    raise ValueError("Missing NEO4J_PASSWORD")

if not NEO4J_URI.startswith("https://"):
    raise ValueError(
        f"NEO4J_URI must start with https:// (got {NEO4J_URI!r}).\n"
        "Use the HTTPS hostname from your Neo4j Aura console, e.g.:\n"
        "  https://xxxxx.databases.neo4j.io"
    )


# -----------------------------------------------------------------------------
# HTTP QUERY API CLIENT  (mirrors backend/neo4j_http.py)
# -----------------------------------------------------------------------------

_QUERY_PATH = "/db/neo4j/query/v2"


class QueryAPI:
    def __init__(self, uri: str, user: str, password: str) -> None:
        parsed = urlparse(uri)
        self.host = parsed.netloc or parsed.path
        self._auth = base64.b64encode(f"{user}:{password}".encode()).decode()

    def execute(self, cypher: str, params: dict | None = None) -> dict:
        body = json.dumps({"statement": cypher, "parameters": params or {}})
        headers = {
            "Authorization": f"Basic {self._auth}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        last_err: Exception | None = None
        for attempt in range(4):
            try:
                conn = http.client.HTTPSConnection(self.host, timeout=30)
                conn.request("POST", _QUERY_PATH, body=body, headers=headers)
                resp = conn.getresponse()
                raw = resp.read()
                conn.close()
                if resp.status in (429, 502, 503, 504):
                    time.sleep(1 + attempt)
                    last_err = RuntimeError(f"HTTP {resp.status}: {raw[:200]!r}")
                    continue
                if resp.status not in (200, 202):
                    raise RuntimeError(f"Query API {resp.status}: {raw[:300]!r}")
                payload = json.loads(raw)
                if payload.get("errors"):
                    raise RuntimeError(f"Cypher error: {payload['errors']}")
                return payload
            except (http.client.HTTPException, ConnectionError, OSError) as e:
                last_err = e
                time.sleep(0.5 * (attempt + 1))
        raise last_err  # type: ignore[misc]


_api = QueryAPI(NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD)


# -----------------------------------------------------------------------------
# SCHEMA — mirrors schema.cypher (idempotent; safe to re-run)
# -----------------------------------------------------------------------------

SCHEMA_QUERIES = [
    # ProteinTarget
    "CREATE CONSTRAINT protein_target_uniprot_unique IF NOT EXISTS "
    "FOR (pt:ProteinTarget) REQUIRE pt.uniprot_id IS UNIQUE",

    "CREATE CONSTRAINT protein_target_id_unique IF NOT EXISTS "
    "FOR (pt:ProteinTarget) REQUIRE pt.id IS UNIQUE",

    "CREATE INDEX protein_target_gene_symbol IF NOT EXISTS "
    "FOR (pt:ProteinTarget) ON (pt.gene_symbol)",

    "CREATE INDEX protein_target_class IF NOT EXISTS "
    "FOR (pt:ProteinTarget) ON (pt.target_class)",

    # Drug
    "CREATE CONSTRAINT drug_id_unique IF NOT EXISTS "
    "FOR (d:Drug) REQUIRE d.id IS UNIQUE",

    "CREATE CONSTRAINT drug_drugbank_id_unique IF NOT EXISTS "
    "FOR (d:Drug) REQUIRE d.drugbank_id IS UNIQUE",

    "CREATE INDEX drug_name_index IF NOT EXISTS "
    "FOR (d:Drug) ON (d.drug_name)",

    "CREATE INDEX drug_approval IF NOT EXISTS "
    "FOR (d:Drug) ON (d.approval_status)",

    "CREATE INDEX drug_fda IF NOT EXISTS "
    "FOR (d:Drug) ON (d.fda_approved)",

    # Mutation
    "CREATE CONSTRAINT mutation_id_unique IF NOT EXISTS "
    "FOR (m:Mutation) REQUIRE m.id IS UNIQUE",

    "CREATE INDEX mutation_gene IF NOT EXISTS "
    "FOR (m:Mutation) ON (m.gene_symbol)",

    # Full-text
    "CREATE FULLTEXT INDEX protein_target_text_search IF NOT EXISTS "
    "FOR (pt:ProteinTarget) ON EACH [pt.gene_symbol, pt.protein_name, pt.target_class, pt.description]",

    "CREATE FULLTEXT INDEX drug_text_search IF NOT EXISTS "
    "FOR (d:Drug) ON EACH [d.drug_name, d.drug_class, d.mechanism]",
]


# -----------------------------------------------------------------------------
# SAMPLE DATA
# -----------------------------------------------------------------------------

PROTEINS: list[dict[str, Any]] = [
    {
        "id": "protein_egfr",
        "gene_symbol": "EGFR",
        "protein_name": "Epidermal Growth Factor Receptor",
        "uniprot_id": "P00533",
        "entrez_gene_id": 1956,
        "ensembl_gene_id": "ENSG00000146648",
        "kegg_id": "hsa:1956",
        "ko_id": "K04361",
        "target_class": "Receptor tyrosine kinase",
        "oncogene": True,
        "tumor_suppressor": False,
        "pathways": ["hsa04010", "hsa04012", "hsa04014", "hsa04150", "hsa04151"],
        "mechanism": "Ligand-activated RTK driving MAPK and PI3K/AKT signaling",
        "description": "Major oncogenic driver in lung adenocarcinoma; mutated in ~15% LUAD",
    },
    {
        "id": "protein_kras",
        "gene_symbol": "KRAS",
        "protein_name": "KRAS Proto-Oncogene, GTPase",
        "uniprot_id": "P01116",
        "entrez_gene_id": 3845,
        "ensembl_gene_id": "ENSG00000133703",
        "kegg_id": "hsa:3845",
        "ko_id": "K07827",
        "target_class": "GTPase",
        "oncogene": True,
        "tumor_suppressor": False,
        "pathways": ["hsa04010", "hsa04012", "hsa04014", "hsa04150", "hsa04151"],
        "mechanism": "Central RAS GTPase; oncogenic mutations lock protein in GTP-bound active state",
        "description": "Most frequently mutated oncogene in LUAD (~30%); KRAS G12C targetable with sotorasib/adagrasib",
    },
    {
        "id": "protein_alk",
        "gene_symbol": "ALK",
        "protein_name": "Anaplastic Lymphoma Kinase",
        "uniprot_id": "Q9UM73",
        "entrez_gene_id": 238,
        "ensembl_gene_id": "ENSG00000171094",
        "kegg_id": "hsa:238",
        "ko_id": "K05119",
        "target_class": "Receptor tyrosine kinase",
        "oncogene": True,
        "tumor_suppressor": False,
        "pathways": ["hsa04010", "hsa04012"],
        "mechanism": "Receptor tyrosine kinase; oncogenic via EML4-ALK fusion driving MAPK/PI3K",
        "description": "EML4-ALK fusions in ~5% LUAD; targetable with crizotinib/alectinib/lorlatinib",
    },
    {
        "id": "protein_tp53",
        "gene_symbol": "TP53",
        "protein_name": "Tumor Protein P53",
        "uniprot_id": "P04637",
        "entrez_gene_id": 7157,
        "ensembl_gene_id": "ENSG00000141510",
        "kegg_id": "hsa:7157",
        "ko_id": "K04451",
        "target_class": "Transcription factor",
        "oncogene": False,
        "tumor_suppressor": True,
        "pathways": ["hsa04115", "hsa04010"],
        "mechanism": "Master transcriptional regulator of cell cycle arrest and apoptosis",
        "description": "Most commonly mutated tumor suppressor in LUAD (~50%); loss enables bypass of apoptosis",
    },
    {
        "id": "protein_met",
        "gene_symbol": "MET",
        "protein_name": "MET Proto-Oncogene, Receptor Tyrosine Kinase",
        "uniprot_id": "P08581",
        "entrez_gene_id": 4233,
        "ensembl_gene_id": "ENSG00000105976",
        "kegg_id": "hsa:4233",
        "ko_id": "K05099",
        "target_class": "Receptor tyrosine kinase",
        "oncogene": True,
        "tumor_suppressor": False,
        "pathways": ["hsa04010", "hsa04014", "hsa04150"],
        "mechanism": "HGF receptor RTK; exon 14 skipping mutations cause MAPK/AKT activation",
        "description": "MET exon 14 alterations in ~3% LUAD; MET amplification is a resistance mechanism to EGFR TKIs",
    },
]

DRUGS: list[dict[str, Any]] = [
    {
        "id": "drug_osimertinib",
        "drug_name": "Osimertinib",
        "drugbank_id": "DB09330",
        "ttd_id": "D0O1XS",
        "chembl_id": "CHEMBL3353410",
        "drug_class": "TKI",
        "drug_type": "Small molecule",
        "approval_status": "FDA_APPROVED",
        "clinical_phase": "Approved",
        "mechanism": "Irreversible EGFR tyrosine kinase inhibitor (3rd gen)",
        "fda_approved": True,
        "oral": True,
        "description": "3rd-generation EGFR TKI; active against T790M resistance mutation; used as 1st-line for EGFR-mutant NSCLC",
        "targets": ["P00533"],  # EGFR uniprot_id
    },
    {
        "id": "drug_erlotinib",
        "drug_name": "Erlotinib",
        "drugbank_id": "DB00530",
        "ttd_id": "D08ADY",
        "chembl_id": "CHEMBL553",
        "drug_class": "TKI",
        "drug_type": "Small molecule",
        "approval_status": "FDA_APPROVED",
        "clinical_phase": "Approved",
        "mechanism": "Reversible EGFR tyrosine kinase inhibitor (1st gen)",
        "fda_approved": True,
        "oral": True,
        "description": "1st-generation EGFR TKI for EGFR-mutant NSCLC",
        "targets": ["P00533"],
    },
    {
        "id": "drug_sotorasib",
        "drug_name": "Sotorasib",
        "drugbank_id": "DB16045",
        "ttd_id": "D0ST4R",
        "chembl_id": "CHEMBL4523582",
        "drug_class": "KRAS inhibitor",
        "drug_type": "Small molecule",
        "approval_status": "FDA_APPROVED",
        "clinical_phase": "Approved",
        "mechanism": "Covalent KRAS G12C inhibitor; locks KRAS in GDP-bound inactive state",
        "fda_approved": True,
        "oral": True,
        "description": "First approved KRAS inhibitor; indicated for KRAS G12C-mutant NSCLC",
        "targets": ["P01116"],  # KRAS
    },
    {
        "id": "drug_adagrasib",
        "drug_name": "Adagrasib",
        "drugbank_id": "DB16726",
        "ttd_id": "D0AG4S",
        "chembl_id": "CHEMBL4594021",
        "drug_class": "KRAS inhibitor",
        "drug_type": "Small molecule",
        "approval_status": "FDA_APPROVED",
        "clinical_phase": "Approved",
        "mechanism": "Covalent KRAS G12C inhibitor",
        "fda_approved": True,
        "oral": True,
        "description": "KRAS G12C inhibitor; also has CNS activity; indicated for KRAS G12C-mutant NSCLC",
        "targets": ["P01116"],
    },
    {
        "id": "drug_alectinib",
        "drug_name": "Alectinib",
        "drugbank_id": "DB09063",
        "ttd_id": "D0AL3C",
        "chembl_id": "CHEMBL2180680",
        "drug_class": "TKI",
        "drug_type": "Small molecule",
        "approval_status": "FDA_APPROVED",
        "clinical_phase": "Approved",
        "mechanism": "Selective ALK/RET tyrosine kinase inhibitor (2nd gen)",
        "fda_approved": True,
        "oral": True,
        "description": "2nd-generation ALK TKI; CNS penetrant; 1st-line for ALK-positive NSCLC",
        "targets": ["Q9UM73"],  # ALK
    },
    {
        "id": "drug_capmatinib",
        "drug_name": "Capmatinib",
        "drugbank_id": "DB12043",
        "ttd_id": "D0CP4T",
        "chembl_id": "CHEMBL2180721",
        "drug_class": "MET inhibitor",
        "drug_type": "Small molecule",
        "approval_status": "FDA_APPROVED",
        "clinical_phase": "Approved",
        "mechanism": "Selective MET tyrosine kinase inhibitor",
        "fda_approved": True,
        "oral": True,
        "description": "MET inhibitor approved for MET exon 14 skipping NSCLC",
        "targets": ["P08581"],  # MET
    },
]

# Clinical mutations with drug sensitivity/resistance annotations
MUTATIONS: list[dict[str, Any]] = [
    {
        "id": "EGFR_L858R",
        "gene_symbol": "EGFR",
        "protein_change": "L858R",
        "dna_change": "c.2573T>G",
        "rsid": "rs121434568",
        "mutation_class": "hotspot",
        "effect_direction": "gain_of_function",
        "oncogenic": True,
        "effect": "activating",
        "hotspot": True,
        "cancer_type": ["LUAD", "NSCLC"],
        "luad_prevalence": 0.13,
        "target_uniprot": "P00533",
    },
    {
        "id": "EGFR_T790M",
        "gene_symbol": "EGFR",
        "protein_change": "T790M",
        "dna_change": "c.2369C>T",
        "rsid": "rs121434569",
        "mutation_class": "hotspot",
        "effect_direction": "gain_of_function",
        "oncogenic": True,
        "effect": "activating",
        "hotspot": True,
        "cancer_type": ["LUAD", "NSCLC"],
        "luad_prevalence": 0.05,
        "target_uniprot": "P00533",
    },
    {
        "id": "KRAS_G12C",
        "gene_symbol": "KRAS",
        "protein_change": "G12C",
        "dna_change": "c.34G>T",
        "rsid": "rs121913530",
        "mutation_class": "hotspot",
        "effect_direction": "gain_of_function",
        "oncogenic": True,
        "effect": "activating",
        "hotspot": True,
        "cancer_type": ["LUAD", "NSCLC", "CRC"],
        "luad_prevalence": 0.14,
        "target_uniprot": "P01116",
    },
    {
        "id": "MET_exon14",
        "gene_symbol": "MET",
        "protein_change": "exon14_skip",
        "dna_change": None,
        "rsid": None,
        "mutation_class": "splice",
        "effect_direction": "gain_of_function",
        "oncogenic": True,
        "effect": "activating",
        "hotspot": True,
        "cancer_type": ["LUAD", "NSCLC"],
        "luad_prevalence": 0.03,
        "target_uniprot": "P08581",
    },
]

# Drug → Mutation clinical evidence (TREATS edges)
DRUG_MUTATION_EVIDENCE: list[dict[str, Any]] = [
    {
        "drug_id": "drug_osimertinib",
        "mutation_id": "EGFR_L858R",
        "evidence_level": "FDA_APPROVED",
        "response_type": "sensitive",
        "disease": "LUAD",
        "pmid": "27825636",
        "source": "oncokb",
    },
    {
        "drug_id": "drug_osimertinib",
        "mutation_id": "EGFR_T790M",
        "evidence_level": "FDA_APPROVED",
        "response_type": "sensitive",
        "disease": "LUAD",
        "pmid": "25970023",
        "source": "oncokb",
    },
    {
        "drug_id": "drug_erlotinib",
        "mutation_id": "EGFR_L858R",
        "evidence_level": "FDA_APPROVED",
        "response_type": "sensitive",
        "disease": "LUAD",
        "pmid": "15118073",
        "source": "oncokb",
    },
    {
        "drug_id": "drug_sotorasib",
        "mutation_id": "KRAS_G12C",
        "evidence_level": "FDA_APPROVED",
        "response_type": "sensitive",
        "disease": "LUAD",
        "pmid": "34596074",
        "source": "oncokb",
    },
    {
        "drug_id": "drug_adagrasib",
        "mutation_id": "KRAS_G12C",
        "evidence_level": "FDA_APPROVED",
        "response_type": "sensitive",
        "disease": "LUAD",
        "pmid": "35658005",
        "source": "oncokb",
    },
    {
        "drug_id": "drug_capmatinib",
        "mutation_id": "MET_exon14",
        "evidence_level": "FDA_APPROVED",
        "response_type": "sensitive",
        "disease": "LUAD",
        "pmid": "32877583",
        "source": "oncokb",
    },
]

# ProteinTarget → Pathway membership (bridges therapeutic layer to KEGG layer)
# kegg_id must match a Pathway node already in the graph (loaded by main pipeline)
PROTEIN_PATHWAY_MEMBERSHIPS: list[dict[str, str]] = [
    {"protein_id": "protein_egfr", "kegg_id": "hsa04010"},
    {"protein_id": "protein_egfr", "kegg_id": "hsa04012"},
    {"protein_id": "protein_egfr", "kegg_id": "hsa04014"},
    {"protein_id": "protein_egfr", "kegg_id": "hsa04150"},
    {"protein_id": "protein_kras", "kegg_id": "hsa04010"},
    {"protein_id": "protein_kras", "kegg_id": "hsa04014"},
    {"protein_id": "protein_kras", "kegg_id": "hsa04150"},
    {"protein_id": "protein_alk",  "kegg_id": "hsa04010"},
    {"protein_id": "protein_alk",  "kegg_id": "hsa04012"},
    {"protein_id": "protein_tp53", "kegg_id": "hsa04115"},
    {"protein_id": "protein_met",  "kegg_id": "hsa04010"},
    {"protein_id": "protein_met",  "kegg_id": "hsa04014"},
]


# -----------------------------------------------------------------------------
# CYPHER
# -----------------------------------------------------------------------------

UPSERT_PROTEIN = """
MERGE (pt:ProteinTarget {uniprot_id: $uniprot_id})
SET
    pt.id               = $id,
    pt.gene_symbol      = $gene_symbol,
    pt.protein_name     = $protein_name,
    pt.entrez_gene_id   = $entrez_gene_id,
    pt.ensembl_gene_id  = $ensembl_gene_id,
    pt.kegg_id          = $kegg_id,
    pt.ko_id            = $ko_id,
    pt.target_class     = $target_class,
    pt.oncogene         = $oncogene,
    pt.tumor_suppressor = $tumor_suppressor,
    pt.pathways         = $pathways,
    pt.mechanism        = $mechanism,
    pt.description      = $description
"""

UPSERT_DRUG = """
MERGE (d:Drug {id: $id})
SET
    d.drug_name       = $drug_name,
    d.drugbank_id     = $drugbank_id,
    d.ttd_id          = $ttd_id,
    d.chembl_id       = $chembl_id,
    d.drug_class      = $drug_class,
    d.drug_type       = $drug_type,
    d.approval_status = $approval_status,
    d.clinical_phase  = $clinical_phase,
    d.mechanism       = $mechanism,
    d.fda_approved    = $fda_approved,
    d.oral            = $oral,
    d.description     = $description
"""

UPSERT_MUTATION = """
MERGE (m:Mutation {id: $id})
SET
    m.gene_symbol      = $gene_symbol,
    m.protein_change   = $protein_change,
    m.dna_change       = $dna_change,
    m.rsid             = $rsid,
    m.mutation_class   = $mutation_class,
    m.effect_direction = $effect_direction,
    m.oncogenic        = $oncogenic,
    m.effect           = $effect,
    m.hotspot          = $hotspot,
    m.cancer_type      = $cancer_type,
    m.luad_prevalence  = $luad_prevalence
"""

CREATE_TARGETS_EDGE = """
MATCH (d:Drug {id: $drug_id})
MATCH (pt:ProteinTarget {uniprot_id: $uniprot_id})
MERGE (d)-[r:TARGETS]->(pt)
SET
    r.mechanism      = $mechanism,
    r.evidence_level = $evidence_level,
    r.source         = $source
"""

CREATE_AFFECTS_EDGE = """
MATCH (m:Mutation {id: $mutation_id})
MATCH (pt:ProteinTarget {uniprot_id: $target_uniprot})
MERGE (m)-[r:AFFECTS]->(pt)
SET
    r.effect           = m.effect,
    r.gain_of_function = (m.effect_direction = 'gain_of_function'),
    r.loss_of_function = (m.effect_direction = 'loss_of_function'),
    r.source           = 'oncokb'
"""

CREATE_TREATS_EDGE = """
MATCH (d:Drug {id: $drug_id})
MATCH (m:Mutation {id: $mutation_id})
MERGE (d)-[r:TREATS]->(m)
SET
    r.evidence_level = $evidence_level,
    r.response_type  = $response_type,
    r.disease        = $disease,
    r.pmid           = $pmid,
    r.source         = $source
"""

# Only creates the edge if the Pathway node already exists in the graph.
CREATE_PARTICIPATES_IN_EDGE = """
MATCH (pt:ProteinTarget {id: $protein_id})
MATCH (p:Pathway {kegg_id: $kegg_id})
MERGE (pt)-[r:PARTICIPATES_IN]->(p)
SET r.pathway_id = $kegg_id
"""


# -----------------------------------------------------------------------------
# FUNCTIONS
# -----------------------------------------------------------------------------

def create_schema() -> None:
    for query in SCHEMA_QUERIES:
        try:
            _api.execute(query)
        except RuntimeError as e:
            # Constraint/index already exists — not an error
            if "already exists" not in str(e).lower():
                raise


def upsert_proteins() -> None:
    for protein in PROTEINS:
        _api.execute(UPSERT_PROTEIN, protein)
        print(f"  ProteinTarget: {protein['gene_symbol']} ({protein['uniprot_id']})")


def upsert_drugs() -> None:
    for drug in DRUGS:
        _api.execute(UPSERT_DRUG, drug)
        print(f"  Drug: {drug['drug_name']}")


def upsert_mutations() -> None:
    for mut in MUTATIONS:
        _api.execute(UPSERT_MUTATION, mut)
        print(f"  Mutation: {mut['id']}")


def create_targets_edges() -> None:
    for drug in DRUGS:
        for uniprot_id in drug["targets"]:
            _api.execute(CREATE_TARGETS_EDGE, {
                "drug_id":        drug["id"],
                "uniprot_id":     uniprot_id,
                "mechanism":      drug["mechanism"],
                "evidence_level": drug["approval_status"],
                "source":         "TTD/DrugBank",
            })
            print(f"  TARGETS: {drug['drug_name']} → {uniprot_id}")


def create_affects_edges() -> None:
    for mut in MUTATIONS:
        if mut.get("target_uniprot"):
            _api.execute(CREATE_AFFECTS_EDGE, {
                "mutation_id":    mut["id"],
                "target_uniprot": mut["target_uniprot"],
            })
            print(f"  AFFECTS: {mut['id']} → {mut['target_uniprot']}")


def create_treats_edges() -> None:
    for ev in DRUG_MUTATION_EVIDENCE:
        _api.execute(CREATE_TREATS_EDGE, ev)
        print(f"  TREATS: {ev['drug_id']} → {ev['mutation_id']} ({ev['evidence_level']})")


def create_participates_in_edges() -> None:
    for mem in PROTEIN_PATHWAY_MEMBERSHIPS:
        try:
            _api.execute(CREATE_PARTICIPATES_IN_EDGE, mem)
            print(f"  PARTICIPATES_IN: {mem['protein_id']} → {mem['kegg_id']}")
        except RuntimeError:
            print(f"  PARTICIPATES_IN (skipped — Pathway {mem['kegg_id']} not in graph yet): {mem['protein_id']}")


# -----------------------------------------------------------------------------
# MAIN
# -----------------------------------------------------------------------------

def main() -> None:
    print("Creating schema constraints and indexes...")
    create_schema()

    print("\nUpserting ProteinTarget nodes...")
    upsert_proteins()

    print("\nUpserting Drug nodes...")
    upsert_drugs()

    print("\nUpserting Mutation nodes...")
    upsert_mutations()

    print("\nCreating TARGETS edges (Drug → ProteinTarget)...")
    create_targets_edges()

    print("\nCreating AFFECTS edges (Mutation → ProteinTarget)...")
    create_affects_edges()

    print("\nCreating TREATS edges (Drug → Mutation)...")
    create_treats_edges()

    print("\nCreating PARTICIPATES_IN edges (ProteinTarget → Pathway)...")
    create_participates_in_edges()

    print("\nNeo4j graph update complete.")


if __name__ == "__main__":
    main()
