#!/usr/bin/env python3
"""Step 2 - CPTAC-LUAD somatic mutations -> harmonized schema.

NOTE: these are PATIENT TUMOR samples, not cell lines (sample_type='tumor').

Pulls LUAD somatic mutations via the `cptac` package and maps them to the
common schema. Run this in an environment with open internet, because cptac
downloads its data on first use (this is blocked inside the Cowork sandbox).

    pip install cptac pandas
    python 02_cptac_luad.py --out-dir ./output

If you already have a CPTAC MAF on disk, skip the package and pass it:
    python 02_cptac_luad.py --maf /path/to/cptac_luad_somatic.maf --out-dir ./output
"""
import argparse
import sys
from pathlib import Path

import pandas as pd

from common import OUT_DIR, SCHEMA, normalize_protein_change


def map_maf(df: pd.DataFrame) -> pd.DataFrame:
    """Map a MAF-like frame (CPTAC or generic) to the harmonized schema."""
    cols = {c.lower(): c for c in df.columns}

    def pick(*names):
        for n in names:
            if n.lower() in cols:
                return cols[n.lower()]
        return None

    sid = pick("Tumor_Sample_Barcode", "Patient_ID", "case_id", "Sample_ID")
    gene = pick("Hugo_Symbol", "Gene", "HugoSymbol")
    pc = pick("HGVSp_Short", "Protein_Change", "ProteinChange", "HGVSp")
    vclass = pick("Variant_Classification", "VariantClassification", "VariantInfo")
    if sid is None or gene is None:
        sys.exit(f"[cptac] could not find sample/gene columns in: {list(df.columns)[:20]}")

    out = pd.DataFrame({
        "sample_id": df[sid].astype(str),
        "source": "CPTAC-LUAD",
        "sample_type": "tumor",
        "sample_name": df[sid].astype(str),
        "gene": df[gene].astype(str),
        "protein_change": df[pc].map(normalize_protein_change) if pc else "",
        "variant_class": df[vclass].astype(str) if vclass else "",
        "is_hotspot": False,
    })
    return out[SCHEMA].drop_duplicates()


def from_package() -> pd.DataFrame:
    import cptac
    lu = cptac.Luad()
    # pick a source that provides somatic mutations (e.g. 'washu', 'harmonized')
    try:
        sources = lu.list_data_sources()
        print("[cptac] data sources:\n", sources)
    except Exception:
        pass
    last_err = None
    for src in ("washu", "harmonized", "broad", "mssm"):
        try:
            df = lu.get_somatic_mutation(src)
            print(f"[cptac] got somatic_mutation from '{src}': {df.shape}")
            return df.reset_index()
        except Exception as e:
            last_err = e
    raise SystemExit(f"[cptac] no somatic_mutation source worked: {last_err}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--maf", type=Path, help="local CPTAC MAF/CSV instead of cptac pkg")
    ap.add_argument("--out-dir", type=Path, default=OUT_DIR)
    args = ap.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    if args.maf:
        sep = "\t" if args.maf.suffix.lower() in (".maf", ".tsv", ".txt") else ","
        raw = pd.read_csv(args.maf, sep=sep, comment="#", low_memory=False)
    else:
        raw = from_package()

    out = map_maf(raw)
    path = args.out_dir / "cptac_luad_mutations_long.csv"
    out.to_csv(path, index=False)
    print(f"[cptac] rows {len(out):,}  samples {out['sample_id'].nunique()}  -> {path}")


if __name__ == "__main__":
    main()
