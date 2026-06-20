"""
CPTAC LUAD Data Downloader
===========================
Downloads LUAD lung cancer data from CPTAC via the PDC (Proteomics Data Commons).

Data types downloaded:
  - Clinical / patient metadata
  - Proteomics (protein abundance, TMT)
  - Genomics (somatic mutations, copy number variation)
  - Bonus: Phosphoproteomics, Transcriptomics (RNA-seq) if available

Requirements:
    pip install cptac pandas

Usage:
    python download_cptac_luad.py

Output:
    Creates ./cptac_luad/ directory with CSV files for each data type.

Source: CPTAC LUAD Discovery Study (PDC000153) via https://pdc.cancer.gov
"""

import os
import sys
import json
from pathlib import Path
from datetime import datetime

# ── 1. Auto-install cptac if missing ─────────────────────────────────────────
try:
    import cptac
    import pandas as pd
except ImportError:
    import subprocess
    print("Installing required packages...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "cptac", "pandas"])
    import cptac
    import pandas as pd

print(f"cptac version: {cptac.__version__}")
print(f"pandas version: {pd.__version__}")

# ── 2. Setup output directory ─────────────────────────────────────────────────
OUT_DIR = Path(__file__).parent / "cptac_luad"
OUT_DIR.mkdir(exist_ok=True)
print(f"\nOutput directory: {OUT_DIR.resolve()}\n")

# ── 3. Download the LUAD dataset from PDC ────────────────────────────────────
print("=" * 60)
print("Downloading CPTAC LUAD dataset from PDC...")
print("(This may take several minutes on first run — files are cached locally)")
print("=" * 60)

cptac.download(dataset="Luad")
luad = cptac.Luad()

# ── 4. Helper: save a dataframe with logging ──────────────────────────────────
manifest = []

def save(df, name: str, description: str):
    if df is None or df.empty:
        print(f"  [SKIP] {name}: empty / not available")
        return
    path = OUT_DIR / f"{name}.csv"
    df.to_csv(path)
    size_kb = path.stat().st_size / 1024
    rows, cols = df.shape
    manifest.append({
        "file": path.name,
        "description": description,
        "rows": rows,
        "columns": cols,
        "size_kb": round(size_kb, 1),
    })
    print(f"  [OK]   {path.name}  ({rows} rows x {cols} cols, {size_kb:.1f} KB)")

# ── 5. Clinical / Patient Metadata ───────────────────────────────────────────
print("\n── Clinical / Patient Metadata ──")
try:
    save(luad.get_clinical(), "clinical", "Patient demographics, survival, pathology, treatment")
except Exception as e:
    print(f"  [ERR]  clinical: {e}")

# ── 6. Proteomics (Protein Abundance) ────────────────────────────────────────
print("\n── Proteomics (Protein Abundance) ──")
try:
    save(luad.get_proteomics(), "proteomics", "TMT-labeled protein abundance (log2 ratio)")
except Exception as e:
    print(f"  [ERR]  proteomics: {e}")

# ── 7. Genomics ───────────────────────────────────────────────────────────────
print("\n── Genomics ──")
try:
    save(luad.get_somatic_mutation(), "somatic_mutations", "Somatic mutations (MAF-derived, per sample x gene)")
except Exception as e:
    print(f"  [ERR]  somatic_mutations: {e}")

try:
    save(luad.get_CNV(), "copy_number_variation", "Gene-level copy number variation (GISTIC2)")
except Exception as e:
    print(f"  [ERR]  copy_number_variation: {e}")

# ── 8. Bonus data types ───────────────────────────────────────────────────────
print("\n── Additional Data Types ──")

bonus = [
    ("get_phosphoproteomics",  "phosphoproteomics",  "Phosphorylation site-level abundance"),
    ("get_transcriptomics",    "transcriptomics",    "RNA-seq gene expression (RPKM)"),
    ("get_acetylproteomics",   "acetylproteomics",   "Lysine acetylation site abundance"),
    ("get_miRNA",              "miRNA",              "miRNA expression"),
    ("get_lipidomics",         "lipidomics",         "Lipid species abundance"),
]

for method, fname, desc in bonus:
    try:
        df = getattr(luad, method)()
        save(df, fname, desc)
    except AttributeError:
        print(f"  [N/A]  {fname}: method not available in this cptac version")
    except Exception as e:
        print(f"  [ERR]  {fname}: {e}")

# ── 9. Write manifest ─────────────────────────────────────────────────────────
manifest_path = OUT_DIR / "manifest.json"
with open(manifest_path, "w") as f:
    json.dump({
        "dataset": "CPTAC LUAD Discovery Study",
        "pdc_study_id": "PDC000153",
        "source": "https://pdc.cancer.gov",
        "downloaded_at": datetime.utcnow().isoformat() + "Z",
        "cptac_version": cptac.__version__,
        "files": manifest,
    }, f, indent=2)

# ── 10. Summary ───────────────────────────────────────────────────────────────
total_kb = sum(m["size_kb"] for m in manifest)
print(f"\n{'=' * 60}")
print(f"Download complete!")
print(f"  Files saved : {len(manifest)}")
print(f"  Total size  : {total_kb / 1024:.2f} MB")
print(f"  Location    : {OUT_DIR.resolve()}")
print(f"{'=' * 60}\n")

print("Files:")
for m in manifest:
    print(f"  {m['file']:<40}  {m['rows']:>5} rows  {m['size_kb']:>8.1f} KB  — {m['description']}")

print(f"\nManifest saved to: {manifest_path}")
