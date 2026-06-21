#!/usr/bin/env python3
"""Step 3 - TCGA-LUAD somatic mutations -> harmonized schema.

NOTE: PATIENT TUMOR samples, not cell lines (sample_type='tumor').

Two ways to get the data (run in an environment with open internet; both the
cBioPortal API and S3 datahub are blocked inside the Cowork sandbox):

  A) cBioPortal REST API (no download of a tarball):
        pip install bravado pandas        # or use requests directly
        python 03_tcga_luad.py --mode api

  B) Local MAF you already downloaded (cBioPortal study
     'luad_tcga_pan_can_atlas_2018' -> data_mutations.txt, or an MC3/GDC MAF):
        python 03_tcga_luad.py --maf /path/to/data_mutations.txt
"""
import argparse
import sys
from pathlib import Path

import pandas as pd

from common import OUT_DIR, SCHEMA, normalize_protein_change

STUDY = "luad_tcga_pan_can_atlas_2018"
CBIO = "https://www.cbioportal.org/api"


def map_maf(df: pd.DataFrame) -> pd.DataFrame:
    cols = {c.lower(): c for c in df.columns}

    def pick(*names):
        for n in names:
            if n.lower() in cols:
                return cols[n.lower()]
        return None

    sid = pick("Tumor_Sample_Barcode", "sampleId", "patientId", "case_id")
    gene = pick("Hugo_Symbol", "hugoGeneSymbol", "gene")
    pc = pick("HGVSp_Short", "proteinChange", "Protein_Change", "HGVSp")
    vclass = pick("Variant_Classification", "mutationType", "variantClassification")
    if sid is None or gene is None:
        sys.exit(f"[tcga] missing sample/gene columns in: {list(df.columns)[:20]}")

    out = pd.DataFrame({
        "sample_id": df[sid].astype(str),
        "source": "TCGA-LUAD",
        "sample_type": "tumor",
        "sample_name": df[sid].astype(str),
        "gene": df[gene].astype(str),
        "protein_change": df[pc].map(normalize_protein_change) if pc else "",
        "variant_class": df[vclass].astype(str) if vclass else "",
        "is_hotspot": False,
    })
    return out[SCHEMA].drop_duplicates()


def from_api() -> pd.DataFrame:
    """Fetch all mutations in the study via the cBioPortal REST API."""
    import requests
    prof = f"{STUDY}_mutations"
    sample_list = f"{STUDY}_all"
    url = f"{CBIO}/molecular-profiles/{prof}/mutations/fetch"
    body = {"sampleListId": sample_list}
    r = requests.post(url, params={"projection": "DETAILED"}, json=body, timeout=120)
    r.raise_for_status()
    data = r.json()
    rows = [{
        "Tumor_Sample_Barcode": m.get("sampleId"),
        "Hugo_Symbol": (m.get("gene") or {}).get("hugoGeneSymbol"),
        "HGVSp_Short": m.get("proteinChange"),
        "Variant_Classification": m.get("mutationType"),
    } for m in data]
    print(f"[tcga] API returned {len(rows)} mutation rows")
    return pd.DataFrame(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["api"], help="fetch from cBioPortal API")
    ap.add_argument("--maf", type=Path, help="local MAF / data_mutations.txt")
    ap.add_argument("--out-dir", type=Path, default=OUT_DIR)
    args = ap.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    if args.maf:
        sep = "\t" if args.maf.suffix.lower() in (".maf", ".tsv", ".txt") else ","
        raw = pd.read_csv(args.maf, sep=sep, comment="#", low_memory=False)
    elif args.mode == "api":
        raw = from_api()
    else:
        sys.exit("Pass --maf PATH or --mode api")

    out = map_maf(raw)
    path = args.out_dir / "tcga_luad_mutations_long.csv"
    out.to_csv(path, index=False)
    print(f"[tcga] rows {len(out):,}  samples {out['sample_id'].nunique()}  -> {path}")


if __name__ == "__main__":
    main()
