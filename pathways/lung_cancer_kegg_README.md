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

---

## JSONL Usage (Python)
```python
import json

with open("lung_cancer_pathways_graph.jsonl") as f:
    records = [json.loads(line) for line in f if line.strip()]

meta  = [r for r in records if r["record_type"] == "meta"][0]
nodes = [r for r in records if r["record_type"] == "node"]
edges = [r for r in records if r["record_type"] == "edge"]

# Filter activated pathways
activated = [n for n in nodes if n["status"] == "activated"]

# Get all edges from MAPK
mapk_edges = [e for e in edges if e["source"] == "MAPK_signaling"]
```

## TOML Usage (Python)
```python
import tomllib

with open("lung_cancer_pathways_graph.toml", "rb") as f:
    graph = tomllib.load(f)

nodes = graph["nodes"]   # list of dicts
edges = graph["edges"]   # list of dicts
```

## JSON Graph Usage (NetworkX)
```python
import json, networkx as nx

with open("lung_cancer_pathways_graph.json") as f:
    data = json.load(f)

G = nx.DiGraph()
for n in data["nodes"]:
    G.add_node(n["id"], **n)
for e in data["edges"]:
    G.add_edge(e["source"], e["target"], **e)

print(nx.info(G))
```
