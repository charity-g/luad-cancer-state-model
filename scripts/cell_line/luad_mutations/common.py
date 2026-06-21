"""Shared config + harmonized schema for the LUAD mutation pipeline.

Harmonized long-format schema (one row per sample-variant):
    sample_id      : str   - cell line ModelID (DepMap) or patient/tumor barcode
    source         : str   - 'DepMap' | 'CPTAC-LUAD' | 'TCGA-LUAD'
    sample_type    : str   - 'cell_line' (DepMap) | 'tumor' (CPTAC/TCGA)
    sample_name    : str   - human-readable name (cell line name / patient id)
    gene           : str   - HGNC symbol
    protein_change : str   - e.g. 'p.G12C' (may be '' for gene-level-only calls)
    variant_class  : str   - e.g. 'Missense_Mutation', 'Hotspot', 'LoF', ...
    is_hotspot     : bool
"""
from pathlib import Path

# --- paths -------------------------------------------------------------------
# Folder holding the DepMap CSVs. Override with --depmap-dir on the CLI.
DEPMAP_DIR = Path(
    r"C:\Users\Hello\Documents\code2026\virtual_cell\luad-cancer-state-model\local_data\dep_map"
)
# Where outputs are written.
OUT_DIR = Path(__file__).resolve().parent / "output"

LUAD_SUBTYPE = "Lung Adenocarcinoma"   # Model.csv OncotreeSubtype value
LUAD_ONCOTREE_CODE = "LUAD"            # Model.csv OncotreeCode value (alt filter)

SCHEMA = [
    "sample_id",
    "source",
    "sample_type",
    "sample_name",
    "gene",
    "protein_change",
    "variant_class",
    "is_hotspot",
]


def normalize_protein_change(pc: str) -> str:
    """Normalize protein-change notation to 'p.XXX' form."""
    if pc is None:
        return ""
    pc = str(pc).strip()
    if pc in ("", "nan", "NaN", ".", "-"):
        return ""
    if not pc.startswith("p."):
        pc = "p." + pc.lstrip("p")
    return pc


def empty_frame():
    import pandas as pd
    return pd.DataFrame(columns=SCHEMA)
