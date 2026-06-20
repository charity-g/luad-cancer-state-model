#!/usr/bin/env python3
"""
upload_init.py
==============
Loads all graph data sources into Neo4j using the schema defined in
schema.cypher and NEO4J_SCHEMA.md.

Sources loaded (in order):
  1. schema.cypher          -- constraints + indexes
  2. KEGG pathway graphs    -- Gene, Compound, Pathway nodes + within-pathway edges
  3. lung_cancer_pathways_graph.json  -- Pathway nodes (DEG stats) + pathway edges
  4. luad_perturbation_layer.json     -- augmented Pathway, Gene, Mutation + pert edges
  5. DepMap Model.csv       -- CellLine nodes + MODELS edges

Usage:
    pip install neo4j pandas
    python scripts/init_neo4j/upload_init.py

    # Custom connection
    NEO4J_URI=bolt://localhost:7687 NEO4J_USER=neo4j NEO4J_PASS=password \\
        python scripts/init_neo4j/upload_init.py --wipe
"""

import json
import os
import re
import glob
import argparse
import csv as _csv
from pathlib import Path

from neo4j import GraphDatabase

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parent.parent.parent

URI    = os.environ.get("NEO4J_URI",  "bolt://localhost:7687")
USER   = os.environ.get("NEO4J_USER", "neo4j")
PASSWD = os.environ.get("NEO4J_PASS", "password")

SCHEMA_FILE      = ROOT / "scripts" / "init_neo4j" / "schema.cypher"
KEGG_DIR         = ROOT / "pathways"
LUNG_GRAPH       = ROOT / "pathways" / "lung_cancer_pathways_graph.json"
PERT_LAYER       = ROOT / "pathways" / "luad_perturbation_layer.json"
DEPMAP_MODEL_CSV = ROOT / "local_data" / "dep_map" / "Model.csv"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _first_symbol(kegg_label: str) -> str:
    """Extract primary HGNC symbol from KEGG gene label.
    'KRAS, RASK2, NS3...' -> 'KRAS'
    """
    return kegg_label.split(",")[0].strip().split(" ")[0].strip()


def _kegg_rel_types(edge_type: str, subtypes: list[dict]) -> list[str]:
    """Map KEGG edge type + subtypes to Neo4j relationship type strings."""
    if edge_type == "GErel":
        return ["REGULATES_EXPRESSION_OF"]
    if edge_type == "PCrel":
        return ["BINDS_COMPOUND"]
    if edge_type == "component_of":
        return ["COMPONENT_OF"]
    subtype_map = {
        "activation":          "ACTIVATES",
        "inhibition":          "INHIBITS",
        "phosphorylation":     "PHOSPHORYLATES",
        "dephosphorylation":   "DEPHOSPHORYLATES",
        "binding/association": "BINDS",
        "ubiquitination":      "UBIQUITINATES",
        "methylation":         "METHYLATES",
        "indirect effect":     "ACTIVATES",
        "missing interaction": "ACTIVATES",
        "expression":          "REGULATES_EXPRESSION_OF",
        "compound":            "BINDS_COMPOUND",
    }
    rels = [subtype_map.get(s.get("name", ""), "ACTIVATES") for s in subtypes]
    return rels if rels else ["ACTIVATES"]


def _pathway_rel_type(etype: str) -> str:
    return {
        "activates":     "ACTIVATES_PATHWAY",
        "represses":     "REPRESSES_PATHWAY",
        "shared_DEG":    "SHARES_DEG_WITH",
        "downstream_of": "DOWNSTREAM_OF",
        "crosstalk":     "CROSSTALK_WITH",
    }.get(etype, "SHARES_DEG_WITH")


def _apply_schema(session):
    """Execute CREATE CONSTRAINT / CREATE INDEX statements from schema.cypher."""
    text = SCHEMA_FILE.read_text(encoding="utf-8")
    executed = 0
    for stmt in text.split(";"):
        lines = [l for l in stmt.splitlines() if not l.strip().startswith("//")]
        clean = "\n".join(lines).strip()
        if clean.upper().startswith(("CREATE CONSTRAINT", "CREATE INDEX")):
            session.run(clean)
            executed += 1
    print(f"  {executed} constraints/indexes applied")


def _nan_to_none(v):
    """Convert float NaN / 'nan' string to None for Neo4j."""
    if v is None:
        return None
    try:
        import math
        f = float(v)
        return None if math.isnan(f) or math.isinf(f) else f
    except (TypeError, ValueError):
        s = str(v)
        return None if s.lower() in ("nan", "none", "") else s


# ---------------------------------------------------------------------------
# Step 1 — Schema
# ---------------------------------------------------------------------------

def apply_schema(session):
    print("[1/5] Applying schema ...")
    _apply_schema(session)


# ---------------------------------------------------------------------------
# Step 2 — KEGG individual pathway graphs
# ---------------------------------------------------------------------------

def load_kegg_graphs(session):
    graphs = sorted(glob.glob(str(KEGG_DIR / "hsa*" / "hsa*_graph.json")))
    print(f"[2/5] Loading {len(graphs)} KEGG pathway graphs ...")

    for gpath in graphs:
        with open(gpath, encoding="utf-8") as f:
            g = json.load(f)

        meta       = g["meta"]
        pathway_id = meta["pathway_id"]
        print(f"  {pathway_id}: {meta['title'][:60]}")

        # Pathway node from meta
        session.run("""
            MERGE (p:Pathway {kegg_id: $kid})
            SET p.title      = $title,
                p.node_count = $nc,
                p.edge_count = $ec,
                p.kgml_url   = $kgml,
                p.entry_page = $ep
        """, kid=pathway_id, title=meta["title"],
             nc=meta["node_count"], ec=meta["edge_count"],
             kgml=meta.get("kgml_url", ""), ep=meta.get("entry_page", ""))

        entry_index = {n["id"]: n for n in g["nodes"]}

        # Nodes
        for node in g["nodes"]:
            ntype = node.get("type", "")

            if ntype == "gene":
                raw   = node.get("label", "")
                sym   = _first_symbol(raw)
                kids  = re.findall(r"hsa:\d+", node.get("name", ""))
                if sym and re.match(r"^[A-Z0-9]", sym):
                    session.run("""
                        MERGE (g:Gene {symbol: $sym})
                        ON CREATE SET g.kegg_ids     = $kids,
                                      g.name_aliases = $aliases
                        ON MATCH  SET g.kegg_ids     = $kids
                        WITH g
                        MERGE (p:Pathway {kegg_id: $pid})
                        MERGE (g)-[:PARTICIPATES_IN {pathway_id: $pid}]->(p)
                    """, sym=sym, kids=kids, aliases=[raw], pid=pathway_id)

            elif ntype == "compound":
                cid  = node.get("label", node["id"])
                name = node.get("graphics", {}).get("name", cid)
                session.run("""
                    MERGE (c:Compound {id: $id})
                    SET c.name = $name, c.kegg_id = $id, c.link = $link
                """, id=cid, name=name, link=node.get("link", ""))

            elif ntype == "map":
                ref = node.get("name", "").replace("path:", "")
                if ref.startswith("hsa"):
                    session.run("""
                        MERGE (p:Pathway {kegg_id: $kid})
                        SET p.label = coalesce(p.label, $label)
                    """, kid=ref, label=node.get("label", ref))

        # Edges
        for edge in g["edges"]:
            src_node = entry_index.get(edge["source"])
            tgt_node = entry_index.get(edge["target"])
            if not src_node or not tgt_node:
                continue

            etype    = edge.get("type", "PPrel")
            subtypes = edge.get("subtypes", [])
            subnames = [s.get("name", "") for s in subtypes]
            indirect = "indirect effect" in subnames

            for rel_type in _kegg_rel_types(etype, subtypes):
                st = src_node.get("type", "")
                tt = tgt_node.get("type", "")

                if st == "gene" and tt == "gene":
                    ss = _first_symbol(src_node.get("label", ""))
                    ts = _first_symbol(tgt_node.get("label", ""))
                    if ss and ts and re.match(r"^[A-Z0-9]", ss) and re.match(r"^[A-Z0-9]", ts):
                        session.run(f"""
                            MATCH (s:Gene {{symbol: $ss}})
                            MATCH (t:Gene {{symbol: $ts}})
                            MERGE (s)-[r:{rel_type} {{pathway_id: $pid}}]->(t)
                            SET r.subtype  = $sub,
                                r.indirect = $ind,
                                r.source   = 'kegg'
                        """, ss=ss, ts=ts, pid=pathway_id,
                             sub=subnames[0] if subnames else "",
                             ind=indirect)

                elif st == "gene" and tt == "compound" and rel_type == "BINDS_COMPOUND":
                    ss  = _first_symbol(src_node.get("label", ""))
                    cid = tgt_node.get("label", tgt_node["id"])
                    if ss and cid:
                        session.run("""
                            MATCH (g:Gene {symbol: $sym})
                            MATCH (c:Compound {id: $cid})
                            MERGE (g)-[r:BINDS_COMPOUND {pathway_id: $pid}]->(c)
                            SET r.source = 'kegg'
                        """, sym=ss, cid=cid, pid=pathway_id)

                elif etype == "component_of" and st == "gene":
                    ss = _first_symbol(src_node.get("label", ""))
                    ts = _first_symbol(tgt_node.get("label", ""))
                    if ss and ts and ss != ts and re.match(r"^[A-Z0-9]", ts):
                        session.run("""
                            MATCH (s:Gene {symbol: $ss})
                            MERGE (t:Gene {symbol: $ts})
                            MERGE (s)-[r:COMPONENT_OF {pathway_id: $pid}]->(t)
                            SET r.source = 'kegg'
                        """, ss=ss, ts=ts, pid=pathway_id)


# ---------------------------------------------------------------------------
# Step 3 — Lung cancer pathways graph
# ---------------------------------------------------------------------------

def load_lung_cancer_graph(session):
    print("[3/5] Loading lung_cancer_pathways_graph ...")
    with open(LUNG_GRAPH, encoding="utf-8") as f:
        data = json.load(f)

    nodes = data.get("nodes", [])
    edges = data.get("edges", [])
    node_id_to_kegg = {n["id"]: n.get("kegg_id", "") for n in nodes}

    for n in nodes:
        session.run("""
            MERGE (p:Pathway {kegg_id: $kid})
            SET p.id                 = $id,
                p.label              = $label,
                p.status             = $status,
                p.q_value            = $qv,
                p.deg_count          = $dc,
                p.upregulated_degs   = $up,
                p.downregulated_degs = $dn,
                p.impact_factor      = $imp,
                p.key_genes          = $kg,
                p.description        = $desc
        """, kid=n.get("kegg_id", ""), id=n.get("id", ""),
             label=n.get("label", ""), status=n.get("status"),
             qv=n.get("q_value"), dc=n.get("deg_count"),
             up=n.get("upregulated_degs"), dn=n.get("downregulated_degs"),
             imp=n.get("impact_factor"), kg=n.get("key_genes", []),
             desc=n.get("description", ""))

    for e in edges:
        rt = _pathway_rel_type(e["type"])
        sk = node_id_to_kegg.get(e["source"], e["source"])
        tk = node_id_to_kegg.get(e["target"], e["target"])
        session.run(f"""
            MATCH (s:Pathway {{kegg_id: $sk}})
            MATCH (t:Pathway {{kegg_id: $tk}})
            MERGE (s)-[r:{rt} {{edge_id: $eid}}]->(t)
            SET r.shared_genes = $sg,
                r.gene_ids     = $gi,
                r.description  = $desc,
                r.source       = 'lung_cancer_graph'
        """, sk=sk, tk=tk, eid=e["id"],
             sg=e.get("shared_genes", []), gi=e.get("gene_ids", []),
             desc=e.get("description", ""))


# ---------------------------------------------------------------------------
# Step 4 — LUAD perturbation layer
# ---------------------------------------------------------------------------

def load_perturbation_layer(session):
    print("[4/5] Loading luad_perturbation_layer ...")
    with open(PERT_LAYER, encoding="utf-8") as f:
        data = json.load(f)

    pathway_nodes  = data.get("pathway_nodes",  [])
    gene_nodes     = data.get("gene_nodes",     [])
    mutation_nodes = data.get("mutation_nodes", [])
    pert_edges     = data.get("perturbation_edges", [])

    pathway_kegg = {n["id"]: n.get("kegg_id", "") for n in pathway_nodes}

    # Augment pathway nodes
    for n in pathway_nodes:
        session.run("""
            MERGE (p:Pathway {kegg_id: $kid})
            SET p.mean_pathway_crispr_effect_luad = $crispr,
                p.n_essential_genes_luad          = $ness,
                p.inferred_state                  = $state,
                p.perturbation_sources            = $srcs
        """, kid=n.get("kegg_id", ""),
             crispr=n.get("mean_pathway_crispr_effect_luad"),
             ness=n.get("n_essential_genes_luad", 0),
             state=n.get("inferred_state"),
             srcs=n.get("perturbation_sources", []))

    # Gene nodes
    for n in gene_nodes:
        session.run("""
            MERGE (g:Gene {symbol: $sym})
            SET g.entrez_id               = $eid,
                g.mean_crispr_effect_luad = $ce,
                g.std_crispr_effect_luad  = $ces,
                g.n_luad_crispr_measured  = $nm,
                g.mean_dep_prob_luad      = $dp,
                g.is_essential_luad       = $ess,
                g.mean_expression_luad    = $ex,
                g.std_expression_luad     = $exs,
                g.mean_cn_luad            = $cn,
                g.cn_status_luad          = $cns
        """, sym=n["symbol"], eid=n.get("entrez_id"),
             ce=n.get("mean_crispr_effect_luad"), ces=n.get("std_crispr_effect_luad"),
             nm=n.get("n_luad_crispr_measured"), dp=n.get("mean_dep_prob_luad"),
             ess=n.get("is_essential_luad"), ex=n.get("mean_expression_luad"),
             exs=n.get("std_expression_luad"), cn=n.get("mean_cn_luad"),
             cns=n.get("cn_status_luad"))

    # Mutation nodes
    for n in mutation_nodes:
        session.run("""
            MERGE (m:Mutation {id: $id})
            SET m.label            = $label,
                m.mutation_class   = $mc,
                m.effect_direction = $ed,
                m.gene_symbol      = $gene,
                m.luad_prevalence  = $prev,
                m.luad_n_positive  = $np,
                m.luad_n_total     = $nt
        """, id=n["id"], label=n["label"], mc=n["mutation_class"],
             ed=n["effect_direction"], gene=n.get("gene", ""),
             prev=n.get("luad_prevalence"), np=n.get("luad_n_positive"),
             nt=n.get("luad_n_total"))

    # Perturbation edges
    for e in pert_edges:
        etype = e.get("type", "")
        eid   = e["id"]

        if etype == "mutates":
            sym = e["target"].replace("gene_", "")
            session.run("""
                MATCH (m:Mutation {id: $src})
                MATCH (g:Gene {symbol: $sym})
                MERGE (m)-[r:MUTATES {edge_id: $eid}]->(g)
                SET r.effect_direction = $ed,
                    r.luad_prevalence  = $prev,
                    r.description      = $desc,
                    r.source           = 'depmap'
            """, src=e["source"], sym=sym, eid=eid,
                 ed=e.get("effect_direction", ""),
                 prev=e.get("luad_prevalence"),
                 desc=e.get("description", ""))

        elif etype == "member_of":
            sym = e["source"].replace("gene_", "")
            kid = pathway_kegg.get(e["target"], e["target"])
            session.run("""
                MATCH (g:Gene {symbol: $sym})
                MATCH (p:Pathway {kegg_id: $kid})
                MERGE (g)-[r:MEMBER_OF {edge_id: $eid}]->(p)
                SET r.source = 'lung_cancer_graph'
            """, sym=sym, kid=kid, eid=eid)

        elif etype == "perturbs":
            kid = pathway_kegg.get(e["target"], e["target"])
            session.run("""
                MATCH (m:Mutation {id: $src})
                MATCH (p:Pathway {kegg_id: $kid})
                MERGE (m)-[r:PERTURBS {edge_id: $eid}]->(p)
                SET r.effect_direction   = $ed,
                    r.luad_prevalence    = $prev,
                    r.via_gene           = $via,
                    r.mean_crispr_effect = $ce,
                    r.is_gene_essential  = $ess,
                    r.description        = $desc,
                    r.source             = 'depmap'
            """, src=e["source"], kid=kid, eid=eid,
                 ed=e.get("effect_direction", ""),
                 prev=e.get("luad_prevalence"),
                 via=e.get("via_gene", ""),
                 ce=e.get("mean_crispr_effect"),
                 ess=e.get("is_gene_essential"),
                 desc=e.get("description", ""))

        elif etype == "crispr_validates":
            sym = e["source"].replace("gene_", "")
            kid = pathway_kegg.get(e["target"], e["target"])
            session.run("""
                MATCH (g:Gene {symbol: $sym})
                MATCH (p:Pathway {kegg_id: $kid})
                MERGE (g)-[r:CRISPR_VALIDATES {edge_id: $eid}]->(p)
                SET r.mean_crispr_effect = $ce,
                    r.mean_dep_prob      = $dp,
                    r.is_essential       = $ess,
                    r.source             = 'depmap'
            """, sym=sym, kid=kid, eid=eid,
                 ce=e.get("mean_crispr_effect"),
                 dp=e.get("mean_dep_prob"),
                 ess=e.get("is_essential"))


# ---------------------------------------------------------------------------
# Step 5 — DepMap cell lines
# ---------------------------------------------------------------------------

def load_cell_lines(session):
    print("[5/5] Loading LUAD cell lines ...")
    import pandas as pd

    # Disease node
    session.run("""
        MERGE (d:Disease {id: "LUAD"})
        SET d.name = "Lung Adenocarcinoma",
            d.oncotree_code = "LUAD",
            d.oncotree_lineage = "Lung"
    """)

    model_df = pd.read_csv(DEPMAP_MODEL_CSV)
    luad_df  = model_df[model_df["OncotreeCode"] == "LUAD"]
    luad_ids = set(luad_df["ModelID"])

    # Detect which cell lines have each data modality
    depmap_dir = DEPMAP_MODEL_CSV.parent

    def _covered_ids(fname: str, luad_ids: set) -> set:
        covered = set()
        try:
            with open(depmap_dir / fname, newline="") as f:
                reader = _csv.reader(f)
                header = next(reader)
                idx = header.index("ModelID") if "ModelID" in header else 0
                for row in reader:
                    mid = row[idx] if idx < len(row) else ""
                    if mid in luad_ids:
                        covered.add(mid)
        except Exception:
            pass
        return covered

    crispr_ids = _covered_ids("CRISPRGeneEffect.csv", luad_ids)
    expr_ids   = _covered_ids("OmicsExpressionTPMLogp1HumanProteinCodingGenes.csv", luad_ids)
    cn_ids     = _covered_ids("OmicsCNGeneWGS.csv", luad_ids)

    for _, row in luad_df.iterrows():
        mid = row["ModelID"]

        def _v(col):
            v = row.get(col, None)
            return None if str(v) in ("nan", "None", "") else v

        session.run("""
            MERGE (cl:CellLine {model_id: $mid})
            SET cl.name                  = $name,
                cl.sex                   = $sex,
                cl.age                   = $age,
                cl.primary_or_metastatic = $pom,
                cl.collection_site       = $site,
                cl.has_crispr_data       = $hc,
                cl.has_expression_data   = $he,
                cl.has_cn_data           = $hn
            WITH cl
            MATCH (d:Disease {id: "LUAD"})
            MERGE (cl)-[:MODELS]->(d)
        """, mid=mid, name=str(_v("CellLineName") or ""),
             sex=str(_v("Sex") or ""),
             age=float(row["Age"]) if str(row.get("Age", "nan")) != "nan" else None,
             pom=str(_v("PrimaryOrMetastasis") or ""),
             site=str(_v("SampleCollectionSite") or ""),
             hc=mid in crispr_ids, he=mid in expr_ids, hn=mid in cn_ids)

    print(f"  {len(luad_df)} CellLine nodes created, linked to Disease:LUAD")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def print_stats(session):
    print("\n--- Node counts ---")
    for rec in session.run(
        "MATCH (n) RETURN labels(n)[0] AS l, count(*) AS c ORDER BY c DESC"
    ):
        print(f"  {rec['l']:30s} {rec['c']}")

    print("--- Relationship counts ---")
    for rec in session.run(
        "MATCH ()-[r]->() RETURN type(r) AS t, count(*) AS c ORDER BY c DESC"
    ):
        print(f"  {rec['t']:35s} {rec['c']}")


def main():
    parser = argparse.ArgumentParser(description="Load LUAD causal graph into Neo4j")
    parser.add_argument("--wipe", action="store_true",
                        help="DETACH DELETE all nodes before loading")
    parser.add_argument("--uri",  default=URI)
    parser.add_argument("--user", default=USER)
    parser.add_argument("--pass", dest="passwd", default=PASSWD)
    args = parser.parse_args()

    driver = GraphDatabase.driver(args.uri, auth=(args.user, args.passwd))
    print(f"Connected: {args.uri}")

    with driver.session() as session:
        if args.wipe:
            print("Wiping database ...")
            session.run("MATCH (n) DETACH DELETE n")

        apply_schema(session)
        load_kegg_graphs(session)
        load_lung_cancer_graph(session)
        load_perturbation_layer(session)
        load_cell_lines(session)
        print_stats(session)

    driver.close()
    print("\nDone.")


if __name__ == "__main__":
    main()
