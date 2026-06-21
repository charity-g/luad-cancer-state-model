#!/usr/bin/env python3
"""Step 1 - DepMap LUAD cell line -> gene mutation mapping.

Join the somatic-mutation calls to Model.csv, keep only Lung Adenocarcinoma
cell lines, and emit the harmonized long-format table plus a per-cell-line
grouped view (cell line -> list of (gene, protein_change)).

Source preference for the mutation calls (uses the first that exists):
  1. OmicsSomaticMutations.csv / CCLE_mutations.csv   (per-variant, has ProteinChange)
  2. fallback: OmicsInferredMolecularSubtypes.csv  (specific variants, e.g. 'KRAS p.G12C')
              + OmicsSomaticMutationsMatrixHotspot.csv  (gene-level hotspot 'Yes')

Usage:
    python 01_depmap_luad.py [--depmap-dir DIR] [--out-dir DIR]
"""
import argparse
import sys
from pathlib import Path

import pandas as pd

from common import (
    DEPMAP_DIR, OUT_DIR, LUAD_SUBTYPE, LUAD_ONCOTREE_CODE,
    SCHEMA, normalize_protein_change,
)


def load_luad_models(depmap_dir: Path) -> pd.DataFrame:
    """Return Model rows for LUAD cell lines (ModelID, name, subtype)."""
    for fname in ("Model.csv", "sample_info.csv"):
        p = depmap_dir / fname
        if p.exists():
            m = pd.read_csv(p, low_memory=False)
            break
    else:
        sys.exit(f"[depmap] No Model.csv/sample_info.csv in {depmap_dir}")

    id_col = "ModelID" if "ModelID" in m.columns else "DepMap_ID"
    name_col = next((c for c in ("CellLineName", "StrippedCellLineName",
                                 "stripped_cell_line_name", "CCLE_Name")
                     if c in m.columns), id_col)

    if "OncotreeSubtype" in m.columns:
        mask = m["OncotreeSubtype"] == LUAD_SUBTYPE
        if "OncotreeCode" in m.columns:
            mask |= m["OncotreeCode"] == LUAD_ONCOTREE_CODE
    elif "lineage_subtype" in m.columns:
        mask = m["lineage_subtype"].isin(["LUAD", "lung_adenocarcinoma"])
    else:
        sys.exit("[depmap] Model file has no subtype column to filter LUAD")

    luad = m.loc[mask, [id_col, name_col]].rename(
        columns={id_col: "sample_id", name_col: "sample_name"}
    ).drop_duplicates("sample_id")
    print(f"[depmap] LUAD cell lines: {len(luad)}")
    return luad


def from_long_calls(depmap_dir: Path, luad_ids: set):
    """Preferred path: per-variant OmicsSomaticMutations.csv."""
    for fname in ("OmicsSomaticMutations.csv", "CCLE_mutations.csv"):
        p = depmap_dir / fname
        if p.exists():
            break
    else:
        return None
    print(f"[depmap] using per-variant calls: {p.name}")

    cols = pd.read_csv(p, nrows=0).columns
    id_col = "ModelID" if "ModelID" in cols else "DepMap_ID"
    gene_col = "HugoSymbol" if "HugoSymbol" in cols else "Hugo_Symbol"
    pc_col = next((c for c in ("ProteinChange", "Protein_Change", "HGVSp_Short")
                   if c in cols), None)
    vclass_col = next((c for c in ("VariantInfo", "VariantType",
                                   "Variant_Classification", "VariantClassification")
                       if c in cols), None)
    hot_col = "HotspotName" if "HotspotName" in cols else None

    usecols = [c for c in (id_col, gene_col, pc_col, vclass_col, hot_col) if c]
    rows = []
    for chunk in pd.read_csv(p, usecols=usecols, chunksize=200_000, low_memory=False):
        chunk = chunk[chunk[id_col].isin(luad_ids)]
        if chunk.empty:
            continue
        out = pd.DataFrame({
            "sample_id": chunk[id_col],
            "gene": chunk[gene_col],
            "protein_change": chunk[pc_col].map(normalize_protein_change) if pc_col else "",
            "variant_class": chunk[vclass_col].astype(str) if vclass_col else "",
            "is_hotspot": chunk[hot_col].notna() if hot_col else False,
        })
        rows.append(out)
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()


def from_fallback(depmap_dir: Path, luad_ids: set):
    """Fallback: specific inferred variants + gene-level hotspot matrix."""
    frames = []

    p = depmap_dir / "OmicsInferredMolecularSubtypes.csv"
    if p.exists():
        print(f"[depmap] fallback using: {p.name}")
        df = pd.read_csv(p, low_memory=False)
        idc = df.columns[0]
        df = df[df[idc].isin(luad_ids)]
        long = df.melt(id_vars=idc, var_name="variant", value_name="val")
        long = long[long["val"].astype(str).str.lower().isin(["true", "1", "1.0", "yes"])]

        def split_variant(v):
            v = str(v)
            if " p." in v:
                g, pc = v.split(" p.", 1)
                return g.strip(), "p." + pc.strip(), "Hotspot", True
            if v.endswith("_LoF"):
                return v[:-4], "", "LoF", False
            g = v.split()[0].split("-")[0]
            pc = v[len(g):].strip() if v.startswith(g) else v
            return g, pc, "Other", "Hotspot" in v

        parts = long["variant"].map(split_variant)
        frames.append(pd.DataFrame({
            "sample_id": long[idc].values,
            "gene": [x[0] for x in parts],
            "protein_change": [x[1] for x in parts],
            "variant_class": [x[2] for x in parts],
            "is_hotspot": [x[3] for x in parts],
        }))

    p = depmap_dir / "OmicsSomaticMutationsMatrixHotspot.csv"
    if p.exists():
        print(f"[depmap] fallback using: {p.name}")
        df = pd.read_csv(p, low_memory=False)
        idc = "ModelID" if "ModelID" in df.columns else df.columns[0]
        meta = {"SequencingID", "ModelID", "ModelConditionID",
                "IsDefaultEntryForModel", "IsDefaultEntryForMC"}
        gene_cols = [c for c in df.columns if c not in meta]
        df = df[df[idc].isin(luad_ids)]
        long = df.melt(id_vars=idc, value_vars=gene_cols,
                       var_name="gene_raw", value_name="val")
        long = long[long["val"].astype(str).str.lower().isin(["yes", "1", "1.0", "true"])]
        long["gene"] = long["gene_raw"].str.replace(r"\s*\(\d+\)$", "", regex=True)
        frames.append(pd.DataFrame({
            "sample_id": long[idc].values,
            "gene": long["gene"].values,
            "protein_change": "",
            "variant_class": "Hotspot",
            "is_hotspot": True,
        }))

    if not frames:
        sys.exit("[depmap] No usable mutation source found in folder.")
    return pd.concat(frames, ignore_index=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--depmap-dir", type=Path, default=DEPMAP_DIR)
    ap.add_argument("--out-dir", type=Path, default=OUT_DIR)
    args = ap.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    luad = load_luad_models(args.depmap_dir)
    luad_ids = set(luad["sample_id"])

    calls = from_long_calls(args.depmap_dir, luad_ids)
    if calls is None or calls.empty:
        calls = from_fallback(args.depmap_dir, luad_ids)

    out = (calls
           .merge(luad, on="sample_id", how="left")
           .assign(source="DepMap", sample_type="cell_line"))
    out["protein_change"] = out["protein_change"].fillna("")
    out = out[SCHEMA].drop_duplicates().sort_values(["sample_id", "gene", "protein_change"])

    long_path = args.out_dir / "depmap_luad_mutations_long.csv"
    out.to_csv(long_path, index=False)

    def fmt(r):
        return f"{r.gene} {r.protein_change}".strip() if r.protein_change else r.gene

    grp = (out.assign(call=out.apply(fmt, axis=1))
              .groupby(["sample_id", "sample_name"])["call"]
              .apply(lambda s: "; ".join(sorted(set(s))))
              .reset_index()
              .rename(columns={"call": "mutations"}))
    grp["n_genes"] = out.groupby("sample_id")["gene"].nunique().reindex(grp["sample_id"]).values
    grouped_path = args.out_dir / "depmap_luad_mutations_grouped.csv"
    grp.to_csv(grouped_path, index=False)

    print(f"[depmap] long rows : {len(out):,}  -> {long_path}")
    print(f"[depmap] cell lines: {out['sample_id'].nunique()}  -> {grouped_path}")
    print(f"[depmap] genes     : {out['gene'].nunique()}")


if __name__ == "__main__":
    main()
