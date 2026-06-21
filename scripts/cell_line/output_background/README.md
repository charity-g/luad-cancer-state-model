File	Contents
luad_cell_line_metadata.csv	91 LUAD cell line metadata rows
luad_molecular_subtype_freq.csv	Prevalence of 39 inferred subtypes (TP53_LoF 92%, KRAS p.G12C 11%, EGFR exon19 del 6%, ...)
luad_gene_summary.csv	20,046 genes × hotspot frequency, mean log-TPM, mean copy number, mean CRISPR dependency/effect
luad_driver_gene_stats.csv	Same stats focused on 21 key LUAD drivers
luad_top_dependencies.csv	Top 100 genes by mean CRISPR dependency in LUAD
luad_background_summary.json	Workspace-ready JSON with driver stats, top mutations, top dependencies, subtype prevalence


Key findings in the data: KRAS (37% hotspot freq, dependency 0.75, effect −1.14) and TP53 (68% hotspot freq, low dependency as expected for a TSG) are prominent. EGFR shows high copy number (mean 2.4×) and meaningful dependency (0.23).

What it does: Filters all DepMap 26Q1 files to the 91 LUAD cell lines and computes population-level statistics across 6 data types, then merges them into a unified gene-level summary.