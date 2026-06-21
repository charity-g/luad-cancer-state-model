#!/usr/bin/env python3
"""Step 4 - harmonize DepMap + CPTAC + TCGA into one LUAD mutation table.

Reads whatever step 1-3 outputs exist in --out-dir, concatenates them on the
common schema, and writes:
  luad_mutations_harmonized_long.csv   - one row per sample-variant (all 3 sources)
  luad_mutations_by_sample.csv         - one row per sample: gene(protein) list
  luad_gene_by_sample_matrix.csv       - binary sample x gene presence matrix
  luad_harmonized_summary.csv          - per-source sample / gene / row counts

Usage:
    python 04_harmonize.py [--out-dir DIR]
"""
import argparse
from pathlib import Path

import pandas as pd

from common import OUT_DIR, SCHEMA

INPUTS = [
    "depmap_luad_mutations_long.csv",
    "cptac_luad_mutations_long.csv",
    "tcga_luad_mutations_long.csv",
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", type=Path, default=OUT_DIR)
    args = ap.parse_args()
    od = args.out_dir

    frames = []
    for f in INPUTS:
        p = od / f
        if p.exists():
            df = pd.read_csv(p)
            frames.append(df)
            print(f"[harmonize] + {f}: {len(df):,} rows")
        else:
            print(f"[harmonize] - {f} missing (skipped)")
    if not frames:
        raise SystemExit("[harmonize] no step 1-3 outputs found.")

    allm = pd.concat(frames, ignore_index=True)
    for c in SCHEMA:
        if c not in allm.columns:
            allm[c] = ""
    allm = allm[SCHEMA].fillna({"protein_change": "", "variant_class": ""})
    allm = allm.drop_duplicates().sort_values(["source", "sample_id", "gene", "protein_change"])
    long_path = od / "luad_mutations_harmonized_long.csv"
    allm.to_csv(long_path, index=False)

    # per-sample grouped
    def fmt(r):
        return f"{r.gene} {r.protein_change}".strip() if r.protein_change else r.gene
    by_sample = (allm.assign(call=allm.apply(fmt, axis=1))
                 .groupby(["source", "sample_type", "sample_id", "sample_name"])["call"]
                 .apply(lambda s: "; ".join(sorted(set(s))))
                 .reset_index().rename(columns={"call": "mutations"}))
    by_sample.to_csv(od / "luad_mutations_by_sample.csv", index=False)

    # binary sample x gene matrix
    mat = (allm.assign(v=1)
           .pivot_table(index=["source", "sample_id"], columns="gene",
                        values="v", aggfunc="max", fill_value=0))
    mat.to_csv(od / "luad_gene_by_sample_matrix.csv")

    # summary
    summ = (allm.groupby("source")
            .agg(samples=("sample_id", "nunique"),
                 genes=("gene", "nunique"),
                 rows=("gene", "size"))
            .reset_index())
    summ.to_csv(od / "luad_harmonized_summary.csv", index=False)

    print("\n[harmonize] SUMMARY")
    print(summ.to_string(index=False))
    print(f"\n[harmonize] harmonized long -> {long_path}  ({len(allm):,} rows)")


if __name__ == "__main__":
    main()
