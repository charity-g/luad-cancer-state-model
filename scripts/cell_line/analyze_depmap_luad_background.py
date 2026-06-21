#!/usr/bin/env python3
"""DepMap LUAD background data extractor.

Produces population-level gene statistics across all LUAD cell lines from the
DepMap 26Q1 release. Outputs are intended to populate background scientific data
in the workspace knowledge graph (Neo4j Protein/Mutation/Pathway nodes).

Outputs written to --out-dir (default: output_background/ next to this file):
  luad_cell_line_metadata.csv      - per cell-line metadata + molecular subtype flags
  luad_gene_summary.csv            - per-gene stats across LUAD lines (mutation freq,
                                     mean expression, copy number, CRISPR dependency/effect)
  luad_molecular_subtype_freq.csv  - prevalence of each inferred molecular subtype in LUAD
  luad_top_dependencies.csv        - genes with highest mean dependency in LUAD (sorted)
  luad_background_summary.json     - workspace-ready JSON summary

Usage:
    python analyze_depmap_luad_background.py [--depmap-dir DIR] [--out-dir DIR]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
DEPMAP_DIR = Path(
    r"C:\Users\Hello\Documents\code2026\virtual_cell\luad-cancer-state-model\local_data\dep_map"
)
OUT_DIR = Path(__file__).resolve().parent / "output_background"

LUAD_SUBTYPE = "Lung Adenocarcinoma"
LUAD_ONCOTREE_CODE = "LUAD"

# Key LUAD driver genes for focused reporting
LUAD_DRIVERS = [
    "KRAS", "EGFR", "TP53", "STK11", "KEAP1", "SMAD4", "ALK", "ROS1",
    "MET", "BRAF", "NRAS", "RB1", "CDKN2A", "NKX2-1", "ERBB2",
    "PIK3CA", "PTEN", "MDM2", "FGFR1", "MAP2K1", "ARID1A",
]


# ---------------------------------------------------------------------------
# Step 1 – LUAD cell line metadata
# ---------------------------------------------------------------------------

def load_luad_models(depmap_dir: Path) -> pd.DataFrame:
    p = depmap_dir / "Model.csv"
    if not p.exists():
        sys.exit(f"[ERROR] Model.csv not found in {depmap_dir}")

    m = pd.read_csv(p, low_memory=False)

    mask = pd.Series(False, index=m.index)
    if "OncotreeSubtype" in m.columns:
        mask |= m["OncotreeSubtype"].eq(LUAD_SUBTYPE)
    if "OncotreeCode" in m.columns:
        mask |= m["OncotreeCode"].eq(LUAD_ONCOTREE_CODE)

    luad = m[mask].copy()
    print(f"[models] LUAD cell lines found: {len(luad)}")

    keep = [
        "ModelID", "CellLineName", "StrippedCellLineName",
        "OncotreeSubtype", "OncotreeCode", "OncotreeLineage",
        "Sex", "Age", "PrimaryOrMetastasis", "SampleCollectionSite",
        "ModelSubtypeFeatures", "PatientSubtypeFeatures",
        "Stage", "PatientTreatmentStatus", "GrowthPattern",
    ]
    keep = [c for c in keep if c in luad.columns]
    return luad[keep].drop_duplicates("ModelID").reset_index(drop=True)


# ---------------------------------------------------------------------------
# Step 2 – Molecular subtypes
# ---------------------------------------------------------------------------

def load_molecular_subtypes(depmap_dir: Path, luad_ids: set) -> pd.DataFrame:
    p = depmap_dir / "OmicsInferredMolecularSubtypes.csv"
    if not p.exists():
        print("[subtypes] OmicsInferredMolecularSubtypes.csv not found – skipping")
        return pd.DataFrame()

    df = pd.read_csv(p, low_memory=False)
    id_col = df.columns[0]
    df = df[df[id_col].isin(luad_ids)].copy()
    df = df.rename(columns={id_col: "ModelID"})
    print(f"[subtypes] LUAD lines with subtype data: {len(df)}")
    return df


def summarize_subtypes(subtype_df: pd.DataFrame, n_luad: int) -> pd.DataFrame:
    if subtype_df.empty:
        return pd.DataFrame()

    meta_cols = {"ModelID"}
    subtype_cols = [c for c in subtype_df.columns if c not in meta_cols]

    rows = []
    for col in subtype_cols:
        vals = subtype_df[col]
        n_pos = int(vals.astype(str).isin(["True", "1", "1.0"]).sum())
        n_with_data = int(vals.notna().sum())
        rows.append({
            "subtype": col,
            "n_luad_lines_positive": n_pos,
            "n_luad_lines_with_data": n_with_data,
            "prevalence_among_tested": round(n_pos / n_with_data, 4) if n_with_data else None,
            "prevalence_overall": round(n_pos / n_luad, 4) if n_luad else None,
        })
    return pd.DataFrame(rows).sort_values("n_luad_lines_positive", ascending=False)


# ---------------------------------------------------------------------------
# Step 3 – Hotspot mutation frequency
# ---------------------------------------------------------------------------

def load_hotspot_freq(depmap_dir: Path, luad_ids: set) -> pd.DataFrame:
    p = depmap_dir / "OmicsSomaticMutationsMatrixHotspot.csv"
    if not p.exists():
        print("[hotspot] OmicsSomaticMutationsMatrixHotspot.csv not found – skipping")
        return pd.DataFrame()

    df = pd.read_csv(p, low_memory=False)
    KNOWN_META = {"Unnamed: 0", "ModelID", "SequencingID", "ModelConditionID",
                  "IsDefaultEntryForModel", "IsDefaultEntryForMC"}
    id_col = "ModelID" if "ModelID" in df.columns else df.columns[0]
    df = df[df[id_col].isin(luad_ids)].copy()
    gene_cols = [c for c in df.columns if c not in KNOWN_META]
    n = len(df)

    # strip Entrez IDs like "KRAS (3845)" -> "KRAS"
    clean = {c: c.split(" (")[0] for c in gene_cols}
    df = df.rename(columns=clean)
    gene_cols_clean = list(clean.values())

    binary = (df[gene_cols_clean] > 0)
    result = pd.DataFrame({
        "gene": gene_cols_clean,
        "hotspot_freq_luad": binary.mean(axis=0).values.round(4),
        "n_luad_lines_hotspot": binary.sum(axis=0).values.astype(int),
        "n_luad_lines_screened_hotspot": n,
    })
    print(f"[hotspot] {n} LUAD lines, {len(gene_cols_clean)} genes")
    return result


# ---------------------------------------------------------------------------
# Step 4 – Expression (chunked, large file)
# ---------------------------------------------------------------------------

def load_expression_stats(depmap_dir: Path, luad_ids: set) -> pd.DataFrame:
    p = depmap_dir / "OmicsExpressionTPMLogp1HumanProteinCodingGenes.csv"
    if not p.exists():
        print("[expression] file not found – skipping")
        return pd.DataFrame()

    header_df = pd.read_csv(p, nrows=0)
    all_cols = list(header_df.columns)

    # Actual structure: Unnamed:0, SequencingID, ModelConditionID, ModelID,
    #                   IsDefaultEntryForMC, IsDefaultEntryForModel, <genes>
    KNOWN_META = {"Unnamed: 0", "SequencingID", "ModelConditionID", "ModelID",
                  "IsDefaultEntryForMC", "IsDefaultEntryForModel",
                  "ProfileID", "is_default_entry"}
    id_col = next((c for c in ("ModelID", "ProfileID") if c in all_cols), None)
    gene_cols = [c for c in all_cols if c not in KNOWN_META]

    sum_arr = np.zeros(len(gene_cols), dtype=np.float64)
    sq_arr = np.zeros(len(gene_cols), dtype=np.float64)
    n_count = np.zeros(len(gene_cols), dtype=np.int32)
    luad_rows = 0

    usecols = ([id_col] if id_col else []) + gene_cols
    chunk_size = 50

    print(f"[expression] streaming {p.name} (chunked) ...")
    for chunk in pd.read_csv(p, usecols=usecols, chunksize=chunk_size, low_memory=False):
        if id_col and id_col in chunk.columns:
            chunk = chunk[chunk[id_col].isin(luad_ids)]
        if chunk.empty:
            continue
        vals = chunk[gene_cols].values.astype(float)
        luad_rows += len(chunk)
        valid = ~np.isnan(vals)
        sum_arr += np.nansum(vals, axis=0)
        sq_arr += np.nansum(vals ** 2, axis=0)
        n_count += valid.sum(axis=0)

    if luad_rows == 0:
        print("[expression] no LUAD rows found")
        return pd.DataFrame()

    mean_expr = np.where(n_count > 0, sum_arr / n_count, np.nan)
    std_expr = np.where(
        n_count > 1,
        np.sqrt(np.maximum(0, sq_arr / n_count - mean_expr ** 2)),
        np.nan,
    )

    # Clean gene names: "GENE (ENTREZ)" -> "GENE"
    clean_names = [g.split(" (")[0] for g in gene_cols]

    result = pd.DataFrame({
        "gene": clean_names,
        "mean_expr_logTPM": mean_expr.round(4),
        "std_expr_logTPM": std_expr.round(4),
        "n_luad_lines_expr": n_count,
    })
    print(f"[expression] {luad_rows} LUAD profiles, {len(gene_cols)} genes")
    return result


# ---------------------------------------------------------------------------
# Step 5 – Copy number
# ---------------------------------------------------------------------------

def load_cn_stats(depmap_dir: Path, luad_ids: set) -> pd.DataFrame:
    p = depmap_dir / "OmicsCNGeneWGS.csv"
    if not p.exists():
        print("[copy_number] file not found – skipping")
        return pd.DataFrame()

    header_df = pd.read_csv(p, nrows=0)
    all_cols = list(header_df.columns)
    KNOWN_META = {"Unnamed: 0", "SequencingID", "ModelConditionID", "ModelID",
                  "IsDefaultEntryForMC", "IsDefaultEntryForModel", "ProfileID"}
    id_col = next((c for c in ("ModelID", "ProfileID") if c in all_cols), None)
    gene_cols = [c for c in all_cols if c not in KNOWN_META]

    sum_arr = np.zeros(len(gene_cols), dtype=np.float64)
    n_count = np.zeros(len(gene_cols), dtype=np.int32)
    luad_rows = 0

    usecols = ([id_col] if id_col else []) + gene_cols
    print(f"[copy_number] streaming {p.name} ...")
    for chunk in pd.read_csv(p, usecols=usecols, chunksize=50, low_memory=False):
        if id_col and id_col in chunk.columns:
            chunk = chunk[chunk[id_col].isin(luad_ids)]
        if chunk.empty:
            continue
        vals = chunk[gene_cols].values.astype(float)
        luad_rows += len(chunk)
        sum_arr += np.nansum(vals, axis=0)
        n_count += (~np.isnan(vals)).sum(axis=0)

    if luad_rows == 0:
        return pd.DataFrame()

    clean_names = [g.split(" (")[0] for g in gene_cols]
    result = pd.DataFrame({
        "gene": clean_names,
        "mean_copy_number": np.where(n_count > 0, sum_arr / n_count, np.nan).round(4),
        "n_luad_lines_cn": n_count,
    })
    print(f"[copy_number] {luad_rows} LUAD profiles, {len(gene_cols)} genes")
    return result


# ---------------------------------------------------------------------------
# Step 6 – CRISPR dependency + gene effect
# ---------------------------------------------------------------------------

def _load_crispr_stats(p: Path, luad_ids: set, col_prefix: str) -> pd.DataFrame:
    if not p.exists():
        print(f"[crispr] {p.name} not found – skipping")
        return pd.DataFrame()

    header_df = pd.read_csv(p, nrows=0)
    all_cols = list(header_df.columns)
    # CRISPR files: first col is ModelID (stored as "Unnamed: 0"), rest are genes
    id_col = all_cols[0]
    gene_cols = all_cols[1:]

    sum_arr = np.zeros(len(gene_cols), dtype=np.float64)
    n_count = np.zeros(len(gene_cols), dtype=np.int32)
    luad_rows = 0

    print(f"[crispr] streaming {p.name} ...")
    for chunk in pd.read_csv(p, chunksize=50, low_memory=False):
        chunk = chunk[chunk[id_col].isin(luad_ids)]
        if chunk.empty:
            continue
        vals = chunk[gene_cols].values.astype(float)
        luad_rows += len(chunk)
        sum_arr += np.nansum(vals, axis=0)
        n_count += (~np.isnan(vals)).sum(axis=0)

    if luad_rows == 0:
        return pd.DataFrame()

    clean_names = [g.split(" (")[0] for g in gene_cols]
    result = pd.DataFrame({
        "gene": clean_names,
        f"mean_{col_prefix}": np.where(n_count > 0, sum_arr / n_count, np.nan).round(4),
        f"n_luad_lines_{col_prefix}": n_count,
    })
    print(f"[crispr] {luad_rows} LUAD lines, {len(gene_cols)} genes ({col_prefix})")
    return result


def load_crispr_dependency(depmap_dir: Path, luad_ids: set) -> pd.DataFrame:
    return _load_crispr_stats(
        depmap_dir / "CRISPRGeneDependency.csv", luad_ids, "crispr_dependency"
    )


def load_crispr_effect(depmap_dir: Path, luad_ids: set) -> pd.DataFrame:
    return _load_crispr_stats(
        depmap_dir / "CRISPRGeneEffect.csv", luad_ids, "crispr_effect"
    )


# ---------------------------------------------------------------------------
# Step 7 – Merge into gene-level summary
# ---------------------------------------------------------------------------

def build_gene_summary(
    hotspot: pd.DataFrame,
    expression: pd.DataFrame,
    cn: pd.DataFrame,
    dependency: pd.DataFrame,
    effect: pd.DataFrame,
) -> pd.DataFrame:
    frames = [f for f in [hotspot, expression, cn, dependency, effect] if not f.empty]
    if not frames:
        return pd.DataFrame()

    summary = frames[0]
    for df in frames[1:]:
        summary = summary.merge(df, on="gene", how="outer")

    return summary.sort_values("gene").reset_index(drop=True)


# ---------------------------------------------------------------------------
# Step 8 – Top dependencies
# ---------------------------------------------------------------------------

def top_dependencies(gene_summary: pd.DataFrame, n: int = 100) -> pd.DataFrame:
    if "mean_crispr_dependency" not in gene_summary.columns:
        return pd.DataFrame()
    cols = ["gene", "mean_crispr_dependency", "mean_crispr_effect",
            "hotspot_freq_luad", "mean_expr_logTPM"]
    cols = [c for c in cols if c in gene_summary.columns]
    top = (
        gene_summary[cols]
        .dropna(subset=["mean_crispr_dependency"])
        .sort_values("mean_crispr_dependency", ascending=False)
        .head(n)
        .reset_index(drop=True)
    )
    return top


# ---------------------------------------------------------------------------
# Step 9 – JSON summary for workspace
# ---------------------------------------------------------------------------

def build_json_summary(
    luad_meta: pd.DataFrame,
    subtype_freq: pd.DataFrame,
    gene_summary: pd.DataFrame,
) -> dict:
    n_lines = len(luad_meta)

    driver_stats = []
    if not gene_summary.empty:
        for gene in LUAD_DRIVERS:
            row = gene_summary[gene_summary["gene"] == gene]
            if row.empty:
                continue
            r = row.iloc[0]
            entry: dict = {"gene": gene}
            for col in ["hotspot_freq_luad", "mean_expr_logTPM", "mean_copy_number",
                        "mean_crispr_dependency", "mean_crispr_effect"]:
                if col in r.index and not pd.isna(r[col]):
                    entry[col] = round(float(r[col]), 4)
            driver_stats.append(entry)

    top_mut = []
    if not gene_summary.empty and "hotspot_freq_luad" in gene_summary.columns:
        top_mut = (
            gene_summary[["gene", "hotspot_freq_luad"]]
            .dropna()
            .nlargest(20, "hotspot_freq_luad")
            [["gene", "hotspot_freq_luad"]]
            .assign(hotspot_freq_luad=lambda d: d["hotspot_freq_luad"].round(4))
            .to_dict(orient="records")
        )

    top_dep = []
    if not gene_summary.empty and "mean_crispr_dependency" in gene_summary.columns:
        top_dep = (
            gene_summary[["gene", "mean_crispr_dependency"]]
            .dropna()
            .nlargest(20, "mean_crispr_dependency")
            .assign(mean_crispr_dependency=lambda d: d["mean_crispr_dependency"].round(4))
            .to_dict(orient="records")
        )

    top_subtypes = []
    if not subtype_freq.empty:
        top_subtypes = (
            subtype_freq[["subtype", "n_luad_lines_positive", "prevalence_overall"]]
            .head(20)
            .to_dict(orient="records")
        )

    return {
        "source": "DepMap 26Q1",
        "cancer_type": "Lung Adenocarcinoma (LUAD)",
        "n_luad_cell_lines": n_lines,
        "driver_gene_stats": driver_stats,
        "top_mutated_genes": top_mut,
        "top_crispr_dependencies": top_dep,
        "molecular_subtype_prevalence": top_subtypes,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--depmap-dir", type=Path, default=DEPMAP_DIR,
                    help="Folder containing DepMap CSVs")
    ap.add_argument("--out-dir", type=Path, default=OUT_DIR,
                    help="Output directory")
    args = ap.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n{'='*60}")
    print(f"DepMap LUAD Background Data Extractor")
    print(f"Source: {args.depmap_dir}")
    print(f"Output: {args.out_dir}")
    print(f"{'='*60}\n")

    # 1. LUAD cell lines
    luad_meta = load_luad_models(args.depmap_dir)
    luad_ids = set(luad_meta["ModelID"])
    luad_meta.to_csv(args.out_dir / "luad_cell_line_metadata.csv", index=False)
    print(f"  -> luad_cell_line_metadata.csv ({len(luad_meta)} lines)\n")

    # 2. Molecular subtypes
    subtype_df = load_molecular_subtypes(args.depmap_dir, luad_ids)
    if not subtype_df.empty:
        # Save per-line subtypes
        subtype_df.to_csv(args.out_dir / "luad_molecular_subtypes_per_line.csv", index=False)
    subtype_freq = summarize_subtypes(subtype_df, len(luad_ids))
    if not subtype_freq.empty:
        subtype_freq.to_csv(args.out_dir / "luad_molecular_subtype_freq.csv", index=False)
        print(f"  -> luad_molecular_subtype_freq.csv ({len(subtype_freq)} subtypes)\n")

    # 3. Hotspot mutations
    hotspot = load_hotspot_freq(args.depmap_dir, luad_ids)
    print()

    # 4. Expression
    expression = load_expression_stats(args.depmap_dir, luad_ids)
    print()

    # 5. Copy number
    cn = load_cn_stats(args.depmap_dir, luad_ids)
    print()

    # 6. CRISPR
    dependency = load_crispr_dependency(args.depmap_dir, luad_ids)
    effect = load_crispr_effect(args.depmap_dir, luad_ids)
    print()

    # 7. Gene summary
    gene_summary = build_gene_summary(hotspot, expression, cn, dependency, effect)
    if not gene_summary.empty:
        gene_summary.to_csv(args.out_dir / "luad_gene_summary.csv", index=False)
        print(f"  -> luad_gene_summary.csv ({len(gene_summary)} genes)\n")

    # 8. Top dependencies
    top_dep = top_dependencies(gene_summary)
    if not top_dep.empty:
        top_dep.to_csv(args.out_dir / "luad_top_dependencies.csv", index=False)
        print(f"  -> luad_top_dependencies.csv ({len(top_dep)} genes)\n")

    # 9. Driver gene focused view
    if not gene_summary.empty:
        drivers_df = gene_summary[gene_summary["gene"].isin(LUAD_DRIVERS)]
        drivers_df.to_csv(args.out_dir / "luad_driver_gene_stats.csv", index=False)
        print(f"  -> luad_driver_gene_stats.csv ({len(drivers_df)} driver genes)\n")

    # 10. JSON summary
    summary_json = build_json_summary(luad_meta, subtype_freq, gene_summary)
    json_path = args.out_dir / "luad_background_summary.json"
    with open(json_path, "w", encoding="utf-8") as fh:
        json.dump(summary_json, fh, indent=2, ensure_ascii=False)
    print(f"  -> luad_background_summary.json\n")

    print(f"{'='*60}")
    print(f"Done. All outputs written to: {args.out_dir}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
