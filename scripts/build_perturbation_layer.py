#!/usr/bin/env python3
"""
build_perturbation_layer.py
============================
ETL: DepMap CSVs → luad_perturbation_layer.json

Constructs a causal inference overlay on top of the KEGG pathway graph.
Output is a tripartite graph with three node types:

    mutation  →  gene  →  pathway (existing KEGG graph)

New node types:
  - mutation : one per OmicsInferredMolecularSubtypes column (hotspot + LoF)
  - gene     : one per KEGG key_gene, enriched with CRISPR effect / expression / CN

New edge types:
  - mutates       : mutation → gene   (derived from subtype column gene symbol)
  - member_of     : gene → pathway    (derived from KEGG key_genes membership)
  - perturbs      : mutation → pathway (shortcut through gene membership)
  - crispr_validates : gene → pathway (CRISPR effect weight)

Output:
  luad_perturbation_layer.json  — same node/edge schema as KEGG graph, new types

Usage:
    python scripts/build_perturbation_layer.py

    # Override paths
    python scripts/build_perturbation_layer.py \\
        --depmap  local_data/dep_map \\
        --kegg    pathways/lung_cancer_pathways_graph.json \\
        --out     pathways/luad_perturbation_layer.json
"""

import json
import re
import argparse
from pathlib import Path

import pandas as pd
import numpy as np

# ── Paths ─────────────────────────────────────────────────────────────────────

ROOT = Path(__file__).resolve().parent.parent
DEPMAP_DIR  = ROOT / "local_data" / "dep_map"
KEGG_FILE   = ROOT / "pathways" / "lung_cancer_pathways_graph.json"
OUT_FILE    = ROOT / "pathways" / "luad_perturbation_layer.json"

# ── Helpers ───────────────────────────────────────────────────────────────────

def _safe_float(v) -> float | None:
    """Return Python float or None for NaN/inf."""
    try:
        f = float(v)
        return None if (np.isnan(f) or np.isinf(f)) else round(f, 6)
    except (TypeError, ValueError):
        return None


def _gene_from_col(col: str) -> str:
    """Extract gene symbol from DepMap column 'GENE (entrez_id)'."""
    return col.split(" (")[0].strip()


def _entrez_from_col(col: str) -> int | None:
    """Extract Entrez ID from DepMap column 'GENE (entrez_id)'."""
    m = re.search(r"\((\d+)\)", col)
    return int(m.group(1)) if m else None


# effect direction rules per mutation class
MUTATION_DIRECTION = {
    # gain-of-function oncogene hotspots
    "KRAS p.G12D": "gain_of_function",
    "KRAS p.G12C": "gain_of_function",
    "KRAS p.G12":  "gain_of_function",
    "KRAS p.G13":  "gain_of_function",
    "KRAS p.Q61":  "gain_of_function",
    "NRAS p.G12":  "gain_of_function",
    "NRAS p.G13":  "gain_of_function",
    "NRAS p.Q61":  "gain_of_function",
    "HRAS p.G12":  "gain_of_function",
    "HRAS p.G13":  "gain_of_function",
    "HRAS p.Q61":  "gain_of_function",
    "BRAF p.V600E":"gain_of_function",
    "EGFR p.L858R":"gain_of_function",
    "EGFR exon 19 del": "gain_of_function",
    "PIK3CA p.E542": "gain_of_function",
    "PIK3CA p.E545": "gain_of_function",
    "PIK3CA p.H1047": "gain_of_function",
    "JAK2 p.V617F": "gain_of_function",
    "ALK Hotspot":  "gain_of_function",
    "MSI":          "ambiguous",
}

# LoF / fusion defaults
def _infer_direction(col: str) -> str:
    if "_LoF" in col:
        return "loss_of_function"
    if any(f in col for f in ["-", "Fusion", "Fusions"]):
        return "gain_of_function"
    return MUTATION_DIRECTION.get(col, "gain_of_function")


def _gene_from_mutation_col(col: str) -> str | None:
    """Extract gene symbol from OmicsInferredMolecularSubtypes column name."""
    # 'KRAS p.G12D'  → 'KRAS'
    # 'RB1_LoF'      → 'RB1'
    # 'EGFR exon 19 del' → 'EGFR'
    # 'ALK Hotspot'  → 'ALK'
    # 'EWSR1-FLI1'   → None  (fusion; skip single-gene assignment)
    # 'KMT2A Fusions'→ None
    if col == "MSI":
        return None
    if "-" in col and not col.endswith("_LoF"):
        # fusion gene pairs — no single gene
        return None
    if "Fusions" in col:
        return None
    return re.split(r"[ _]", col)[0]


# ── 1. Load KEGG graph ────────────────────────────────────────────────────────

def load_kegg(path: Path) -> tuple[list[dict], list[dict]]:
    with open(path) as f:
        g = json.load(f)
    return g["nodes"], g["edges"]


# ── 2. Load + filter DepMap to LUAD ──────────────────────────────────────────

def load_luad_model_ids(depmap_dir: Path) -> list[str]:
    model = pd.read_csv(depmap_dir / "Model.csv")
    luad = model[model["OncotreeCode"] == "LUAD"]["ModelID"].tolist()
    print(f"  LUAD cell lines: {len(luad)}")
    return luad


# ── 3. Build mutation nodes from OmicsInferredMolecularSubtypes ──────────────

def build_mutation_nodes(depmap_dir: Path, luad_ids: list[str]) -> list[dict]:
    df = pd.read_csv(depmap_dir / "OmicsInferredMolecularSubtypes.csv", index_col=0)
    luad_df = df.loc[df.index.isin(luad_ids)]

    nodes = []
    for col in luad_df.columns:
        vals = luad_df[col]
        # True/False or bool-castable
        prevalence = float(vals.astype(bool).mean())
        mut_id = "mut_" + re.sub(r"[^A-Za-z0-9]", "_", col)
        gene = _gene_from_mutation_col(col)

        nodes.append({
            "id":              mut_id,
            "label":           col,
            "type":            "mutation",
            "mutation_class":  "lof" if "_LoF" in col
                               else ("fusion" if ("-" in col or "Fusion" in col)
                               else ("msi" if col == "MSI" else "hotspot")),
            "effect_direction": _infer_direction(col),
            "gene":            gene,
            "luad_prevalence": round(prevalence, 4),
            "luad_n_positive": int(vals.astype(bool).sum()),
            "luad_n_total":    len(luad_df),
        })

    print(f"  Mutation nodes: {len(nodes)}")
    return nodes


# ── 4. Build gene nodes (key_genes × DepMap) ─────────────────────────────────

def _load_depmap_matrix(
    path: Path,
    target_genes: set[str],
    luad_ids: list[str],
) -> tuple[pd.DataFrame, dict[str, str]]:
    """
    Fast loader for wide DepMap matrices (18-20k columns, 400MB+).

    Strategy: read header with Python csv (instant), build an awk program that
    simultaneously filters to LUAD rows AND selects target-gene columns, pipe
    the tiny output (~91 rows x 92 cols) to pandas. Scanning 400MB with awk
    takes ~4s vs. >40s for pandas usecols on a mounted filesystem.
    """
    import csv
    import io
    import subprocess

    # 1. Read header + first data row to determine which column holds ModelID.
    #    CRISPRGeneEffect: col 0 = ModelID (unnamed, contains "ACH-..." values)
    #    OmicsExpression / OmicsCNGeneWGS: col 0 = row index int, col 3 = ModelID
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
        first_row = next(reader)

    # Auto-detect: if "ModelID" appears in header, use that column; else use col 0
    if "ModelID" in header:
        id_col_idx = header.index("ModelID")       # 0-based Python index
        id_awk_field = id_col_idx + 1              # 1-based awk field
    else:
        id_col_idx = 0
        id_awk_field = 1

    # col_idx_map: gene_symbol -> (1-based awk field, original col name)
    # Skip non-gene metadata columns (those without an entrez ID suffix)
    col_idx_map: dict[str, tuple[int, str]] = {}
    for i, col in enumerate(header, start=1):
        if i == id_awk_field:
            continue
        gene = _gene_from_col(col)
        if gene in target_genes and gene not in col_idx_map:
            col_idx_map[gene] = (i, col)

    if not col_idx_map:
        return pd.DataFrame(), {}

    # 2. Build awk program that filters rows to LUAD ModelIDs and selects columns.
    #    Also deduplicate: for Expression/CN files keep only IsDefaultEntryForModel==Yes.
    luad_set_awk = " || ".join(f'${id_awk_field}=="{mid}"' for mid in luad_ids)

    # For files with an IsDefaultEntryForModel column, add that filter
    if "IsDefaultEntryForModel" in header:
        default_idx = header.index("IsDefaultEntryForModel") + 1
        row_filter = f'({luad_set_awk}) && ${default_idx}=="Yes"'
    else:
        row_filter = f'({luad_set_awk})'

    selected_fields = f"${id_awk_field}"
    selected_header = "ModelID"
    for gene, (fidx, col_name) in sorted(col_idx_map.items(), key=lambda x: x[1][0]):
        selected_fields += f", ${fidx}"
        selected_header += f",{col_name}"

    awk_prog = (
        f'BEGIN {{FS=","; OFS=","}} '
        f'NR==1 {{print "{selected_header}"; next}} '
        f'{row_filter} {{print {selected_fields}}}'
    )

    # 3. Run awk, pipe tiny output to pandas
    result = subprocess.run(
        ["awk", awk_prog, str(path)],
        capture_output=True, text=True, check=True,
    )
    if not result.stdout.strip():
        return pd.DataFrame(), {}

    luad_df = pd.read_csv(io.StringIO(result.stdout), index_col=0)
    matched = {_gene_from_col(c): c for c in luad_df.columns}
    return luad_df, matched


def build_gene_nodes(
    kegg_nodes: list[dict],
    depmap_dir: Path,
    luad_ids: list[str],
) -> list[dict]:

    # Collect all key_genes + which pathways they belong to
    gene_to_pathways: dict[str, list[str]] = {}
    for n in kegg_nodes:
        for g in n.get("key_genes", []):
            gene_to_pathways.setdefault(g, []).append(n["id"])

    all_genes = sorted(gene_to_pathways.keys())
    target_gene_set = set(all_genes)
    print(f"  Unique key_genes to enrich: {len(all_genes)}")

    # -- CRISPRGeneEffect (usecols only) --
    print("  Loading CRISPRGeneEffect (targeted columns) …")
    ge_luad, ge_col_map = _load_depmap_matrix(
        depmap_dir / "CRISPRGeneEffect.csv", target_gene_set, luad_ids
    )
    print(f"    matched {len(ge_col_map)} genes, {len(ge_luad)} LUAD rows")

    # -- CRISPRGeneDependency (usecols only) --
    print("  Loading CRISPRGeneDependency (targeted columns) …")
    gd_luad, gd_col_map = _load_depmap_matrix(
        depmap_dir / "CRISPRGeneDependency.csv", target_gene_set, luad_ids
    )
    print(f"    matched {len(gd_col_map)} genes, {len(gd_luad)} LUAD rows")

    # -- Expression (usecols only) --
    print("  Loading OmicsExpressionTPMLogp1 (targeted columns) …")
    expr_luad, expr_col_map = _load_depmap_matrix(
        depmap_dir / "OmicsExpressionTPMLogp1HumanProteinCodingGenes.csv",
        target_gene_set, luad_ids,
    )
    print(f"    matched {len(expr_col_map)} genes, {len(expr_luad)} LUAD rows")

    # -- Copy Number (usecols only) --
    print("  Loading OmicsCNGeneWGS (targeted columns) …")
    cn_luad, cn_col_map = _load_depmap_matrix(
        depmap_dir / "OmicsCNGeneWGS.csv", target_gene_set, luad_ids
    )
    print(f"    matched {len(cn_col_map)} genes, {len(cn_luad)} LUAD rows")

    gene_nodes = []
    for gene in all_genes:
        node: dict = {
            "id":    f"gene_{gene}",
            "label": gene,
            "type":  "gene",
            "symbol": gene,
            "pathway_membership": gene_to_pathways[gene],
        }

        # CRISPR effect
        if gene in ge_col_map:
            col_data = ge_luad[ge_col_map[gene]].dropna()
            node["entrez_id"]               = _entrez_from_col(ge_col_map[gene])
            node["mean_crispr_effect_luad"] = _safe_float(col_data.mean())
            node["std_crispr_effect_luad"]  = _safe_float(col_data.std())
            node["n_luad_crispr_measured"]  = int(col_data.count())

        # CRISPR dependency probability
        if gene in gd_col_map:
            dep_data = gd_luad[gd_col_map[gene]].dropna()
            node["mean_dep_prob_luad"]  = _safe_float(dep_data.mean())
            node["is_essential_luad"]   = (
                bool(dep_data.mean() > 0.5) if dep_data.count() > 0 else None
            )

        # Expression
        if gene in expr_col_map:
            expr_data = expr_luad[expr_col_map[gene]].dropna()
            node["mean_expression_luad"] = _safe_float(expr_data.mean())
            node["std_expression_luad"]  = _safe_float(expr_data.std())

        # Copy number
        if gene in cn_col_map:
            cn_data = cn_luad[cn_col_map[gene]].dropna()
            node["mean_cn_luad"] = _safe_float(cn_data.mean())
            # flag likely amplification (>2.5 copies) or deletion (<0.5)
            if node["mean_cn_luad"] is not None:
                if node["mean_cn_luad"] > 2.5:
                    node["cn_status_luad"] = "amplified"
                elif node["mean_cn_luad"] < 0.5:
                    node["cn_status_luad"] = "deleted"
                else:
                    node["cn_status_luad"] = "neutral"

        gene_nodes.append(node)

    essential = sum(1 for g in gene_nodes if g.get("is_essential_luad"))
    print(f"  Gene nodes: {len(gene_nodes)} ({essential} essential in LUAD)")
    return gene_nodes


# ── 5. Build edges ────────────────────────────────────────────────────────────

def build_edges(
    mutation_nodes: list[dict],
    gene_nodes: list[dict],
    kegg_nodes: list[dict],
    depmap_dir: Path,
    luad_ids: list[str],
) -> list[dict]:

    edges = []
    edge_idx = 0

    def _eid():
        nonlocal edge_idx
        edge_idx += 1
        return f"pe{edge_idx:04d}"

    # Index
    gene_index = {g["symbol"]: g for g in gene_nodes}
    pathway_gene_index: dict[str, list[str]] = {}   # pathway_id → [gene symbols]
    for n in kegg_nodes:
        pathway_gene_index[n["id"]] = n.get("key_genes", [])

    # ── 5a. mutates: mutation → gene ─────────────────────────────────────────
    for m in mutation_nodes:
        gene = m.get("gene")
        if gene and gene in gene_index:
            edges.append({
                "id":              _eid(),
                "source":          m["id"],
                "target":          gene_index[gene]["id"],
                "type":            "mutates",
                "effect_direction": m["effect_direction"],
                "luad_prevalence": m["luad_prevalence"],
                "description": (
                    f"{m['label']} alters {gene} "
                    f"({m['effect_direction'].replace('_', ' ')}) "
                    f"in {m['luad_prevalence']*100:.1f}% of LUAD lines"
                ),
            })

    # ── 5b. member_of: gene → pathway ────────────────────────────────────────
    for pathway_id, genes in pathway_gene_index.items():
        for gene in genes:
            if gene in gene_index:
                g = gene_index[gene]
                edges.append({
                    "id":      _eid(),
                    "source":  g["id"],
                    "target":  pathway_id,
                    "type":    "member_of",
                    "description": f"{gene} is a key gene in {pathway_id}",
                })

    # ── 5c. perturbs: mutation → pathway (shortcut) ──────────────────────────
    # For each mutation, find pathways that contain its gene
    for m in mutation_nodes:
        gene = m.get("gene")
        if not gene or gene not in gene_index:
            continue
        g = gene_index[gene]
        for pathway_id in g.get("pathway_membership", []):
            # aggregate CRISPR effect of this gene in this pathway context
            edges.append({
                "id":                  _eid(),
                "source":              m["id"],
                "target":              pathway_id,
                "type":                "perturbs",
                "effect_direction":    m["effect_direction"],
                "luad_prevalence":     m["luad_prevalence"],
                "via_gene":            gene,
                "mean_crispr_effect":  g.get("mean_crispr_effect_luad"),
                "is_gene_essential":   g.get("is_essential_luad"),
                "description": (
                    f"{m['label']} perturbs {pathway_id} via {gene}"
                ),
            })

    # ── 5d. crispr_validates: gene → pathway (weighted by CRISPR essentiality) ─
    for g in gene_nodes:
        effect = g.get("mean_crispr_effect_luad")
        dep    = g.get("mean_dep_prob_luad")
        if effect is None:
            continue
        for pathway_id in g.get("pathway_membership", []):
            edges.append({
                "id":                  _eid(),
                "source":              g["id"],
                "target":              pathway_id,
                "type":                "crispr_validates",
                "mean_crispr_effect":  effect,
                "mean_dep_prob":       dep,
                "is_essential":        g.get("is_essential_luad"),
                "description": (
                    f"{g['symbol']} CRISPR effect {effect:.3f} in LUAD "
                    f"(dep prob {dep:.3f})" if dep is not None
                    else f"{g['symbol']} CRISPR effect {effect:.3f} in LUAD"
                ),
            })

    print(f"  Edges: {len(edges)}")
    by_type: dict[str, int] = {}
    for e in edges:
        by_type[e["type"]] = by_type.get(e["type"], 0) + 1
    for t, n in sorted(by_type.items()):
        print(f"    {t}: {n}")

    return edges


# ── 6. Augment KEGG pathway nodes with DepMap-derived aggregates ──────────────

def augment_pathway_nodes(
    kegg_nodes: list[dict],
    gene_nodes: list[dict],
    mutation_nodes: list[dict],
    perturbation_edges: list[dict],
) -> list[dict]:
    """
    Return copies of KEGG pathway nodes with extra fields:
      - mean_pathway_crispr_effect_luad : mean effect across key genes
      - n_essential_genes_luad          : count of essential key genes
      - top_perturbations_luad          : top-3 mutations by prevalence targeting this pathway
      - inferred_state                  : 'activated' | 'repressed' | 'ambiguous' | None
      - perturbation_sources            : mutation node ids driving inferred_state
    """
    gene_index = {g["symbol"]: g for g in gene_nodes}

    # perturbs edges grouped by target pathway
    pathway_perturbs: dict[str, list[dict]] = {}
    for e in perturbation_edges:
        if e["type"] == "perturbs":
            pathway_perturbs.setdefault(e["target"], []).append(e)

    augmented = []
    for n in kegg_nodes:
        node = dict(n)
        key_genes = n.get("key_genes", [])

        # Aggregate CRISPR across key genes
        effects = [
            gene_index[g]["mean_crispr_effect_luad"]
            for g in key_genes
            if g in gene_index and gene_index[g].get("mean_crispr_effect_luad") is not None
        ]
        node["mean_pathway_crispr_effect_luad"] = (
            round(float(np.mean(effects)), 6) if effects else None
        )
        node["n_essential_genes_luad"] = sum(
            1 for g in key_genes
            if g in gene_index and gene_index[g].get("is_essential_luad")
        )

        # Top perturbations
        perturbs = pathway_perturbs.get(n["id"], [])
        top = sorted(perturbs, key=lambda e: e.get("luad_prevalence", 0), reverse=True)[:3]
        node["top_perturbations_luad"] = [
            {
                "mutation_id":     e["source"],
                "luad_prevalence": e.get("luad_prevalence"),
                "effect_direction": e.get("effect_direction"),
                "via_gene":        e.get("via_gene"),
            }
            for e in top
        ]

        # Infer pathway state from perturbation directions
        gof = sum(1 for e in perturbs if e.get("effect_direction") == "gain_of_function")
        lof = sum(1 for e in perturbs if e.get("effect_direction") == "loss_of_function")
        if gof > 0 and lof == 0:
            node["inferred_state"] = "activated"
        elif lof > 0 and gof == 0:
            node["inferred_state"] = "repressed"
        elif gof > 0 and lof > 0:
            node["inferred_state"] = "ambiguous"
        else:
            node["inferred_state"] = None

        node["perturbation_sources"] = [e["source"] for e in perturbs]

        augmented.append(node)

    return augmented


# ── 7. Propagate causal states through existing KEGG edges ───────────────────

def propagate_causal_states(
    augmented_kegg_nodes: list[dict],
    kegg_edges: list[dict],
) -> list[dict]:
    """
    Single-pass causal propagation along KEGG pathway edges (activates / represses).
    Pathway nodes with inferred_state=None that receive signal from an upstream
    node get an inferred_state derived from the edge type.

    Propagation rules:
      activates edge  + upstream activated  → downstream activated
      activates edge  + upstream repressed  → downstream repressed
      represses edge  + upstream activated  → downstream repressed
      represses edge  + upstream repressed  → downstream activated
      downstream_of   + any upstream state  → inherits upstream state
    """
    state_map = {n["id"]: n.get("inferred_state") for n in augmented_kegg_nodes}
    source_map: dict[str, list[str]] = {n["id"]: list(n.get("perturbation_sources", [])) for n in augmented_kegg_nodes}

    CAUSAL_EDGE_TYPES = {"activates", "represses", "downstream_of"}

    # topological-ish: iterate until stable (≤ 10 passes)
    for _ in range(10):
        changed = False
        for e in kegg_edges:
            if e["type"] not in CAUSAL_EDGE_TYPES:
                continue
            src_state = state_map.get(e["source"])
            tgt_state = state_map.get(e["target"])
            if src_state is None or src_state == "ambiguous":
                continue
            if tgt_state is not None:
                continue  # already has direct perturbation state, don't override

            if e["type"] == "activates":
                new_state = src_state  # activated→activated, repressed→repressed
            elif e["type"] == "represses":
                new_state = "repressed" if src_state == "activated" else "activated"
            else:  # downstream_of
                new_state = src_state

            state_map[e["target"]] = new_state
            source_map[e["target"]].append(f"propagated_from:{e['source']}")
            changed = True

        if not changed:
            break

    # Write back
    result = []
    for n in augmented_kegg_nodes:
        node = dict(n)
        propagated = state_map[n["id"]]
        if propagated != n.get("inferred_state"):
            node["inferred_state"]     = propagated
            node["propagation_source"] = source_map[n["id"]]
        result.append(node)

    return result


# ── Main ──────────────────────────────────────────────────────────────────────

def main(depmap_dir: Path, kegg_file: Path, out_file: Path) -> None:
    print("=" * 60)
    print("DepMap → Perturbation Layer ETL")
    print("=" * 60)

    print("\n[1/7] Loading KEGG graph …")
    kegg_nodes, kegg_edges = load_kegg(kegg_file)
    print(f"  Pathway nodes: {len(kegg_nodes)}, edges: {len(kegg_edges)}")

    print("\n[2/7] Filtering to LUAD cell lines …")
    luad_ids = load_luad_model_ids(depmap_dir)

    print("\n[3/7] Building mutation nodes …")
    mutation_nodes = build_mutation_nodes(depmap_dir, luad_ids)

    print("\n[4/7] Building gene nodes …")
    gene_nodes = build_gene_nodes(kegg_nodes, depmap_dir, luad_ids)

    print("\n[5/7] Building edges …")
    pert_edges = build_edges(mutation_nodes, gene_nodes, kegg_nodes, depmap_dir, luad_ids)

    print("\n[6/7] Augmenting KEGG pathway nodes …")
    augmented_kegg = augment_pathway_nodes(kegg_nodes, gene_nodes, mutation_nodes, pert_edges)

    print("\n[7/7] Propagating causal states …")
    final_kegg = propagate_causal_states(augmented_kegg, kegg_edges)
    activated  = sum(1 for n in final_kegg if n.get("inferred_state") == "activated")
    repressed  = sum(1 for n in final_kegg if n.get("inferred_state") == "repressed")
    ambiguous  = sum(1 for n in final_kegg if n.get("inferred_state") == "ambiguous")
    print(f"  Pathway inferred states → activated:{activated}  repressed:{repressed}  ambiguous:{ambiguous}")

    # ── Assemble output ───────────────────────────────────────────────────────
    output = {
        "meta": {
            "name":        "LUAD Perturbation Layer",
            "description": (
                "Causal inference overlay on LUAD KEGG pathway graph. "
                "Tripartite graph: mutation → gene → pathway. "
                "Augmented KEGG pathway nodes include DepMap-derived aggregates "
                "and inferred causal state from DepMap mutation profiles."
            ),
            "source_kegg":   str(kegg_file),
            "source_depmap": str(depmap_dir),
            "luad_n_cell_lines": len(luad_ids),
            "node_types":   ["mutation", "gene", "pathway"],
            "edge_types":   ["mutates", "member_of", "perturbs", "crispr_validates",
                             "activates", "represses", "downstream_of", "crosstalk", "shared_DEG"],
        },
        "pathway_nodes":  final_kegg,
        "gene_nodes":     gene_nodes,
        "mutation_nodes": mutation_nodes,
        "pathway_edges":  kegg_edges,
        "perturbation_edges": pert_edges,
    }

    out_file.parent.mkdir(parents=True, exist_ok=True)
    with open(out_file, "w") as f:
        json.dump(output, f, indent=2)

    print(f"\nWritten: {out_file}")
    print(f"  pathway_nodes      : {len(final_kegg)}")
    print(f"  gene_nodes         : {len(gene_nodes)}")
    print(f"  mutation_nodes     : {len(mutation_nodes)}")
    print(f"  pathway_edges      : {len(kegg_edges)}")
    print(f"  perturbation_edges : {len(pert_edges)}")
    print("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build LUAD perturbation layer from DepMap")
    parser.add_argument("--depmap", type=Path, default=DEPMAP_DIR)
    parser.add_argument("--kegg",   type=Path, default=KEGG_FILE)
    parser.add_argument("--out",    type=Path, default=OUT_FILE)
    args = parser.parse_args()
    main(args.depmap, args.kegg, args.out)
FILE)
    args = parser.parse_args()
    main(args.depmap, args.kegg, args.out)
 default=KEGG_FILE)
    parser.add_argument("--out",    type=Path, default=OUT_FILE)
    args = parser.parse_args()
    main(args.depmap, args.kegg, args.out)
 final_kegg,
        # New gene-level nodes
        "gene_nodes":     gene_nodes,
        # New mutation nodes
        "mutation_nodes": mutation_nodes,
        # Original KEGG pathway↔pathway edges (preserved)
        "pathway_edges":  kegg_edges,
        # New perturbation layer edges
        "perturbation_edges": pert_edges,
    }

    out_file.parent.mkdir(parents=True, exist_ok=True)
    with open(out_file, "w") as f:
        json.dump(output, f, indent=2)

    print(f"\n✓ Written → {out_file}")
    print(f"  pathway_nodes    : {len(final_kegg)}")
    print(f"  gene_nodes       : {len(gene_nodes)}")
    print(f"  mutation_nodes   : {len(mutation_nodes)}")
    print(f"  pathway_edges    : {len(kegg_edges)}")
    print(f"  perturbation_edges: {len(pert_edges)}")
    print("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build LUAD perturbation layer from DepMap")
    parser.add_argument("--depmap", type=Path, default=DEPMAP_DIR)
    parser.add_argument("--kegg",   type=Path, default=KEGG_FILE)
    parser.add_argument("--out",    type=Path, default=OUT_FILE)
    args = parser.parse_args()
    main(args.depmap, args.kegg, args.out)
