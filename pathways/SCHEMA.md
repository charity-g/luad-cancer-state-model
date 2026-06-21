# pathway graph
multiple pathways, each one a folder with:


## edge csv schema : id,source,target,type,subtypes,source_entry_id,target_entry_id
relation_1,entry_32,entry_30,PPrel,"[{""name"": ""activation"", ""value"": ""-->""}]",32,30

## graph json
"meta": {
    "title": "KEGG EGFR tyrosine kinase inhibitor resistance",
    "entry_page": "https://www.kegg.jp/entry/hsa01521",
    "kgml_url": "https://rest.kegg.jp/get/hsa01521/kgml",
    "reference_entry_id": "hsa01521",
    "pathway_id": "hsa01521",
    "node_count": 77,
    "edge_count": 129
  },
  "nodes": [
    {
      "id": "entry_6",
      "entry_id": 6,
      "label": "Non-small cell lung cancer",
      "type": "map",
      "name": "path:hsa05223",
      "link": "https://www.kegg.jp/dbget-bin/www_bget?hsa05223",
      "graphics": {
        "name": "Non-small cell lung cancer",
        "type": "roundrectangle",
        "fgcolor": "#000000",
        "bgcolor": "#FFFFFF",
        "x": 343,
        "y": 117,
        "width": 102,
        "height": 34
      },
      "component_entry_ids": []
    },

## nodes csv

id,entry_id,label,type,name,link,graphics,component_entry_ids
entry_6,6,Non-small cell lung cancer,map,path:hsa05223,https://www.kegg.jp/dbget-bin/www_bget?hsa05223,"{""name"": ""Non-small cell lung cancer"", ""type"": ""roundrectangle"", ""fgcolor"": ""#000000"", ""bgcolor"": ""#FFFFFF"", ""x"": 343, ""y"": 117, ""width"": 102, ""height"": 34}",[]

# ANOTHER pathway graph with 
# Lung Cancer KEGG Pathway Graph
## File Map

| File | Format | Purpose |
|------|--------|---------|
| lung_cancer_pathways_graph.json  | JSON   | Full graph: meta + nodes[] + edges[] |
| lung_cancer_pathways_graph.jsonl | JSONL  | One record per line (streamable)     |
| lung_cancer_pathways_graph.toml  | TOML   | Config-style; [[nodes]] / [[edges]]  |
| README.md                        | Markdown | This file                          |

---

## Graph Summary

- **Nodes (pathways):** 26
- **Edges (relationships):** 36

### Node status breakdown
- `activated`: 11 pathways
- `crosstalk_hub`: 7 pathways
- `nsclc_enriched`: 6 pathways
- `repressed`: 2 pathways

### Edge type breakdown
- `activates`: 3 edges
- `crosstalk`: 3 edges
- `downstream_of`: 7 edges
- `represses`: 1 edges
- `shared_DEG`: 22 edges

### Most connected pathway nodes (by degree)
- **MAPK signaling pathway** — degree 14 (5 out, 9 in)
- **Chemokine signaling pathway** — degree 7 (5 out, 2 in)
- **Cytokine-cytokine receptor interaction** — degree 5 (4 out, 1 in)
- **Endocytosis** — degree 5 (0 out, 5 in)
- **Vascular smooth muscle contraction** — degree 4 (1 out, 3 in)

---

## Schema

### Node fields
```
id              string   unique snake_case identifier
label           string   human-readable KEGG pathway name
kegg_id         string   e.g. hsa04010
type            string   "pathway" | "gene"
status          string   "activated" | "repressed" | "crosstalk_hub" | "nsclc_enriched"
q_value         float?   (upDEGs - downDEGs) / totalDEGs  (null if not measured)
deg_count       int?     total differentially expressed genes in pathway
upregulated_degs int?
downregulated_degs int?
impact_factor   float?   SPIA impact analysis score
key_genes       string[] major genes involved
description     string   biological context
```

### Edge fields
```
id              string   e.g. "e01"
source          string   node id
target          string   node id
type            string   "crosstalk" | "shared_DEG" | "activates" | "represses" | "downstream_of"
shared_genes    string[] gene symbols bridging the two pathways
gene_ids        int[]    NCBI Entrez gene IDs
description     string   mechanistic explanation
```

# perturbation state:

  "meta": {
    "name": "LUAD Perturbation Layer",
    "description": "Causal inference overlay on LUAD KEGG pathway graph. Tripartite graph: mutation \u2192 gene \u2192 pathway. Augmented KEGG pathway nodes include DepMap-derived aggregates and inferred causal state from DepMap mutation profiles.",
    "source_kegg": "/sessions/admiring-charming-franklin/mnt/luad-cancer-state-model/pathways/lung_cancer_pathways_graph.json",
    "source_depmap": "/sessions/admiring-charming-franklin/mnt/luad-cancer-state-model/local_data/dep_map",
    "luad_n_cell_lines": 91,
    "node_types": [
      "mutation",
      "gene",
      "pathway"
    ],
    "edge_types": [
      "mutates",
      "member_of",
      "perturbs",
      "crispr_validates",
      "activates",
      "represses",
      "downstream_of",
      "crosstalk",
      "shared_DEG"
    ]
  },
  "pathway_nodes": [
    {
      "id": "MAPK_signaling",
      "label": "MAPK signaling pathway",
      "kegg_id": "hsa04010",
      "type": "pathway",
      "status": "activated",
      "q_value": 0.857,
      "deg_count": 14,
      "upregulated_degs": 13,
      "downregulated_degs": 1,
      "impact_factor": null,
      "key_genes": [
        "GADD45B",
        "MAP2K4",
        "MAP2K7",
        "EGFR",
        "KRAS"
      ],
      "description": "Core oncogenic signaling cascade; activated via EGFR/KRAS mutations in NSCLC",
      "mean_pathway_crispr_effect_luad": -0.307702,
      "n_essential_genes_luad": 1,
      "top_perturbations_luad": [
        {
          "mutation_id": "mut_KRAS_p_G12",
          "luad_prevalence": 0.2874,
          "effect_direction": "gain_of_function",
          "via_gene": "KRAS"
        },etc],
        "gene_nodes": [
    {
      "id": "gene_ACTA2",
      "label": "ACTA2",
      "type": "gene",
      "symbol": "ACTA2",
      "pathway_membership": [
        "vascular_smooth_muscle"
      ],
      "entrez_id": 59,
      "mean_crispr_effect_luad": 0.030725,
      "std_crispr_effect_luad": 0.102234,
      "n_luad_crispr_measured": 53,
      "mean_dep_prob_luad": 0.025109,
      "is_essential_luad": false,
      "mean_expression_luad": 1.739611,
      "std_expression_luad": 1.142546,
      "mean_cn_luad": 1.025832,
      "cn_status_luad": "neutral"
    
    }] etc,
    "mutation_nodes": [
    {
      "id": "mut_KRAS_p_G12D",
      "label": "KRAS p.G12D",
      "type": "mutation",
      "mutation_class": "hotspot",
      "effect_direction": "gain_of_function",
      "gene": "KRAS",
      "luad_prevalence": 0.0805,
      "luad_n_positive": 7,
      "luad_n_total": 87
    },etc,
    ],
    "pathway_edges": [
    {
      "id": "e01",
      "source": "MAPK_signaling",
      "target": "cell_cycle",
      "type": "shared_DEG",
      "shared_genes": [
        "GADD45B"
      ],
      "gene_ids": [
        4616
      ],
      "description": "GADD45B bridges MAPK activation and cell cycle repression"
    }, etc]
    , 
    "perturbation_edges": [
    {
      "id": "pe0001",
      "source": "mut_KRAS_p_G12D",
      "target": "gene_KRAS",
      "type": "mutates",
      "effect_direction": "gain_of_function",
      "luad_prevalence": 0.0805,
      "description": "KRAS p.G12D alters KRAS (gain of function) in 8.1% of LUAD lines"
    }, etc],
    }
