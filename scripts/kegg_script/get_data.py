
#!/usr/bin/env python3

"""
KEGG pathway fetcher for selected signaling pathways and core entities.

Requirements:
    pip install requests pandas

Outputs:
    - pathway_summary.csv
    - gene_to_pathways.csv
    - optional KGML files
"""

import os
import requests
import pandas as pd
from collections import defaultdict

BASE_URL = "https://rest.kegg.jp"

# -------------------------------------------------------
# TARGET GENES
# -------------------------------------------------------

pathway_gene_sets = {
    "MAPK": [
        "EGFR", "KRAS", "NRAS", "BRAF", "RAF1",
        "MAP2K1", "MAP2K2", "MAPK3", "MAPK1", "DUSP6"
    ],

    "PI3K_AKT": [
        "PIK3CA", "AKT1", "AKT2", "MTOR",
        "PTEN", "TSC1", "TSC2"
    ],

    "EGFR_SIGNALING": [
        "EGFR", "ERBB2", "ERBB3",
        "GRB2", "SOS1", "SHC1"
    ],

    "P53": [
        "TP53", "MDM2", "CDKN1A",
        "ATM", "ATR", "CHEK1", "CHEK2"
    ],

    "RTK_SIGNALING": [
        "MET", "ALK", "ROS1", "RET",
        "FGFR1", "FGFR2"
    ]
}

# Flatten unique genes
all_genes = sorted(set(
    gene
    for genes in pathway_gene_sets.values()
    for gene in genes
))

# -------------------------------------------------------
# HELPER FUNCTIONS
# -------------------------------------------------------

def kegg_find_gene(symbol, organism="hsa"):
    """
    Convert HGNC symbol -> KEGG gene ID
    """
    url = f"{BASE_URL}/find/genes/{symbol}"
    r = requests.get(url)

    if r.status_code != 200:
        return None

    lines = r.text.strip().split("\n")

    for line in lines:
        if f"; {symbol}" in line or f"{symbol};" in line:
            return line.split("\t")[0]

    return None


def get_gene_pathways(kegg_gene_id):
    """
    Retrieve pathways linked to a KEGG gene.
    """
    url = f"{BASE_URL}/link/pathway/{kegg_gene_id}"
    r = requests.get(url)

    if r.status_code != 200:
        return []

    pathways = []

    for line in r.text.strip().split("\n"):
        if line:
            _, pathway = line.split("\t")
            pathways.append(pathway)

    return pathways


def get_pathway_name(pathway_id):
    """
    Get human-readable pathway name.
    """
    url = f"{BASE_URL}/get/{pathway_id}"
    r = requests.get(url)

    if r.status_code != 200:
        return pathway_id

    for line in r.text.split("\n"):
        if line.startswith("NAME"):
            return line.replace("NAME", "").strip()

    return pathway_id


def download_kgml(pathway_id, outdir="kgml"):
    """
    Download KGML XML file for pathway.
    """
    os.makedirs(outdir, exist_ok=True)

    url = f"{BASE_URL}/get/{pathway_id}/kgml"
    r = requests.get(url)

    if r.status_code == 200:
        outfile = os.path.join(outdir, f"{pathway_id}.xml")

        with open(outfile, "w", encoding="utf-8") as f:
            f.write(r.text)

        return outfile

    return None


# -------------------------------------------------------
# MAIN
# -------------------------------------------------------

gene_to_kegg = {}
gene_to_pathways = defaultdict(list)
pathway_to_genes = defaultdict(list)

print("Mapping genes to KEGG IDs...")

for gene in all_genes:
    kegg_id = kegg_find_gene(gene)

    if kegg_id:
        gene_to_kegg[gene] = kegg_id
        print(f"{gene} -> {kegg_id}")
    else:
        print(f"WARNING: could not map {gene}")

print("\nRetrieving pathways...\n")

for gene, kegg_id in gene_to_kegg.items():

    pathways = get_gene_pathways(kegg_id)

    for pw in pathways:
        gene_to_pathways[gene].append(pw)
        pathway_to_genes[pw].append(gene)

# -------------------------------------------------------
# FILTER RELEVANT PATHWAYS
# -------------------------------------------------------

interesting_keywords = [
    "MAPK",
    "PI3K",
    "AKT",
    "ErbB",
    "EGFR",
    "p53",
    "mTOR",
    "Ras",
    "RTK",
    "FoxO"
]

filtered_rows = []

print("\nRelevant pathways:\n")

for pathway_id, genes in pathway_to_genes.items():

    pathway_name = get_pathway_name(pathway_id)

    if any(k.lower() in pathway_name.lower()
           for k in interesting_keywords):

        print(f"{pathway_id}: {pathway_name}")
        print(f"  Genes: {', '.join(sorted(set(genes)))}")

        filtered_rows.append({
            "pathway_id": pathway_id,
            "pathway_name": pathway_name,
            "genes": ",".join(sorted(set(genes)))
        })

        # OPTIONAL:
        # download KGML files
        download_kgml(pathway_id)

# -------------------------------------------------------
# SAVE OUTPUTS
# -------------------------------------------------------

summary_df = pd.DataFrame(filtered_rows)
summary_df.to_csv("pathway_summary.csv", index=False)

gene_rows = []

for gene, pathways in gene_to_pathways.items():
    for pw in pathways:
        gene_rows.append({
            "gene": gene,
            "pathway": pw
        })

gene_df = pd.DataFrame(gene_rows)
gene_df.to_csv("gene_to_pathways.csv", index=False)

print("\nDone.")
print("Generated:")
print("  - pathway_summary.csv")
print("  - gene_to_pathways.csv")
print("  - kgml/ directory")
