# LUAD cell-line / tumor mutation mapping pipeline

Builds a harmonized "sample -> gene mutation" table for Lung Adenocarcinoma
across three sources:

| source     | sample_type | what it is                         |
|------------|-------------|------------------------------------|
| DepMap     | cell_line   | LUAD cell lines (your local CSVs)  |
| CPTAC-LUAD | tumor       | patient tumors (cptac package)     |
| TCGA-LUAD  | tumor       | patient tumors (cBioPortal / MAF)  |

> Note: only DepMap has actual cell lines. CPTAC and TCGA are patient tumor
> cohorts, harmonized into the same schema with sample_type = "tumor".

## Harmonized schema (long format, one row per sample-variant)
`sample_id, source, sample_type, sample_name, gene, protein_change, variant_class, is_hotspot`

## Steps
```
python 01_depmap_luad.py --depmap-dir <dir> --out-dir ./output_final   # DepMap (local)
python 02_cptac_luad.py  --out-dir ./output_final                      # CPTAC (needs internet)
python 03_tcga_luad.py   --mode api --out-dir ./output_final           # TCGA  (needs internet)
python 04_harmonize.py   --out-dir ./output_final                      # merge all present sources
```
Step 4 merges whichever of steps 1-3 have produced output, so you can run
DepMap now and add CPTAC/TCGA later.

## DepMap data source note
Step 1 prefers the per-variant file `OmicsSomaticMutations.csv`
(columns ModelID, HugoSymbol, ProteinChange, VariantInfo, HotspotName) and will
use it automatically if you drop it into the DepMap folder.

Your folder does NOT currently contain that file, so step 1 falls back to:
  - `OmicsInferredMolecularSubtypes.csv`  -> specific hotspot variants (e.g. KRAS p.G12C)
  - `OmicsSomaticMutationsMatrixHotspot.csv` -> gene-level hotspot calls

=> Current DepMap output is HOTSPOT-LEVEL ONLY (48 genes). To get the full
mutation complement with every protein change, download
`OmicsSomaticMutations.csv` from https://depmap.org/portal/data_page/ (same
release as your other files) into the DepMap folder and re-run step 1.

## CPTAC / TCGA note
These were NOT run here: the Cowork sandbox blocks the cptac data backend,
cBioPortal API, and the S3 datahub. Run steps 2 and 3 on your own machine
(open internet). Both also accept a local MAF via `--maf PATH`.

## Outputs (in output_final/)
- depmap_luad_mutations_long.csv      DepMap long format
- depmap_luad_mutations_grouped.csv   DepMap: cell line -> "; "-joined mutation list
- luad_mutations_harmonized_long.csv  all sources concatenated (long)
- luad_mutations_by_sample.csv        every sample -> mutation list
- luad_gene_by_sample_matrix.csv      binary sample x gene matrix
- luad_harmonized_summary.csv         per-source sample/gene/row counts

## Current run (DepMap only)
91 LUAD cell lines; 82 carry >=1 hotspot/inferred call; 48 genes; 270 rows.
Top genes: TP53 (72), KRAS (62), CDKN2A (36), EGFR (10) - canonical LUAD drivers.
