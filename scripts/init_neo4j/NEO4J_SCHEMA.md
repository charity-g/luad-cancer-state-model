# Neo4j Schema Reference
## LUAD Causal Biological Reasoning System

This document is the authoritative schema reference for the Neo4j graph database.
It is designed to be included in LLM system prompts to enable Cypher query generation
and mechanistic reasoning over LUAD biology.

---

## Data Sources

| Source | File | What it contributes |
|--------|------|---------------------|
| KEGG individual pathways | `pathways/hsa*/hsa*_graph.json` | Gene-level signal flow (activation, inhibition, phosphorylation) within 8 pathways |
| Lung cancer pathway graph | `pathways/lung_cancer_pathways_graph.json` | Pathway-level DEG statistics, crosstalk, causal relationships between 26 LUAD-enriched pathways |
| LUAD perturbation layer | `pathways/luad_perturbation_layer.json` | Mutation prevalence, CRISPR essentiality, causal inference of pathway states from DepMap |
| DepMap Model.csv | `local_data/dep_map/` | 91 LUAD cell line identities |

---

## Node Labels

### `Gene`
A protein-coding gene. Merged across KEGG entries and DepMap data. Primary key: `symbol`.

| Property | Type | Source | Description |
|----------|------|--------|-------------|
| `symbol` | string | KEGG/DepMap | HGNC gene symbol — **primary key** |
| `entrez_id` | integer | DepMap column header | NCBI Entrez gene ID |
| `kegg_ids` | string[] | KEGG | All KEGG gene IDs (e.g. `["hsa:3845"]`) |
| `name_aliases` | string[] | KEGG label field | Gene name aliases from KEGG |
| `mean_crispr_effect_luad` | float | DepMap CRISPRGeneEffect | Mean Chronos score across LUAD lines; more negative = more essential |
| `std_crispr_effect_luad` | float | DepMap | Standard deviation of CRISPR effect |
| `n_luad_crispr_measured` | integer | DepMap | Number of LUAD cell lines with CRISPR data for this gene |
| `mean_dep_prob_luad` | float | DepMap CRISPRGeneDependency | Mean dependency probability (0–1) |
| `is_essential_luad` | boolean | DepMap | True if mean_dep_prob_luad > 0.5 |
| `mean_expression_luad` | float | DepMap OmicsExpression | Mean log(TPM+1) across LUAD lines |
| `std_expression_luad` | float | DepMap | Standard deviation of expression |
| `mean_cn_luad` | float | DepMap OmicsCNGeneWGS | Mean copy number in LUAD |
| `cn_status_luad` | string | DepMap | `"neutral"` / `"amplified"` (>2.5) / `"deleted"` (<0.5) |

**Reasoning use:** Find synthetic lethal targets (`is_essential_luad = true`), amplified oncogenes (`cn_status_luad = "amplified"`), expressed drug targets.

---

### `Pathway`
A KEGG biological pathway. Merged from the lung cancer graph and individual KEGG graphs. Primary key: `kegg_id`.

| Property | Type | Source | Description |
|----------|------|--------|-------------|
| `kegg_id` | string | KEGG | KEGG pathway ID e.g. `"hsa04010"` — **primary key** |
| `id` | string | lung_cancer_graph | Snake-case ID e.g. `"MAPK_signaling"` |
| `label` | string | lung_cancer_graph | Short human-readable name |
| `title` | string | KEGG meta | Full KEGG pathway title |
| `status` | string | lung_cancer_graph | LUAD expression status: `"activated"` / `"repressed"` / `"crosstalk_hub"` / `"nsclc_enriched"` |
| `q_value` | float | lung_cancer_graph | (upDEGs − downDEGs) / totalDEGs |
| `deg_count` | integer | lung_cancer_graph | Total differentially expressed genes |
| `upregulated_degs` | integer | lung_cancer_graph | |
| `downregulated_degs` | integer | lung_cancer_graph | |
| `impact_factor` | float | lung_cancer_graph | SPIA impact analysis score |
| `description` | string | lung_cancer_graph | Biological context |
| `mean_pathway_crispr_effect_luad` | float | perturbation layer | Mean CRISPR effect across key genes |
| `n_essential_genes_luad` | integer | perturbation layer | Count of essential key genes |
| `inferred_state` | string | perturbation layer | Causal state inferred from mutations: `"activated"` / `"repressed"` / `"ambiguous"` |
| `perturbation_sources` | string[] | perturbation layer | Mutation IDs driving the inferred state |
| `node_count` | integer | KEGG graph | Number of entries in KEGG pathway graph |
| `edge_count` | integer | KEGG graph | Number of relations in KEGG pathway graph |

**Reasoning use:** Identify activated/repressed pathways in LUAD context, assess CRISPR vulnerability, find downstream compensation routes.

---

### `Mutation`
A specific genetic alteration observed in LUAD cell lines. Primary key: `id`.

| Property | Type | Source | Description |
|----------|------|--------|-------------|
| `id` | string | perturbation layer | Unique ID e.g. `"mut_KRAS_p_G12C"` — **primary key** |
| `label` | string | perturbation layer | Human-readable e.g. `"KRAS p.G12C"` |
| `mutation_class` | string | perturbation layer | `"hotspot"` / `"lof"` / `"fusion"` / `"msi"` |
| `effect_direction` | string | perturbation layer | `"gain_of_function"` / `"loss_of_function"` / `"ambiguous"` |
| `gene_symbol` | string | perturbation layer | Affected gene HGNC symbol |
| `luad_prevalence` | float | DepMap OmicsInferredMolecularSubtypes | Fraction of LUAD lines carrying this mutation (0–1) |
| `luad_n_positive` | integer | DepMap | Count of positive LUAD lines |
| `luad_n_total` | integer | DepMap | Total LUAD lines tested |

**Reasoning use:** Identify driver mutations in patient context, assess co-occurrence with resistance, model perturbation cascades.

---

### `Compound`
A KEGG chemical compound (metabolite, second messenger). Primary key: `id`.

| Property | Type | Description |
|----------|------|-------------|
| `id` | string | KEGG compound ID e.g. `"C00338"` |
| `name` | string | Compound name |
| `kegg_id` | string | Same as id |
| `link` | string | KEGG URL |

---

### `Drug`
A therapeutic agent. Scaffold for DrugBank / OpenTargets integration. Primary key: `id`.

| Property | Type | Description |
|----------|------|-------------|
| `id` | string | DrugBank ID or canonical name |
| `name` | string | Drug name e.g. `"osimertinib"` |
| `drug_class` | string | `"TKI"` / `"MEKi"` / `"mTORi"` / `"immunotherapy"` etc. |
| `mechanism` | string | Mechanism of action |
| `fda_status` | string | `"approved"` / `"investigational"` |
| `targets` | string[] | Gene symbols (denormalized; also via TARGETS relationship) |

---

### `Disease`
A disease entity. Primary key: `id`.

| Property | Type | Description |
|----------|------|-------------|
| `id` | string | e.g. `"LUAD"` |
| `name` | string | `"Lung Adenocarcinoma"` |
| `oncotree_code` | string | e.g. `"LUAD"` |
| `oncotree_lineage` | string | e.g. `"Lung"` |

---

### `CellLine`
A DepMap LUAD cell line model. Primary key: `model_id`.

| Property | Type | Description |
|----------|------|-------------|
| `model_id` | string | DepMap ID e.g. `"ACH-000012"` |
| `name` | string | Cell line name e.g. `"HCC-827"` |
| `sex` | string | Patient sex |
| `age` | float | Patient age |
| `primary_or_metastatic` | string | `"Primary"` / `"Metastatic"` |
| `collection_site` | string | e.g. `"lung"` / `"pleural_effusion"` |
| `has_crispr_data` | boolean | CRISPR screen available (53/91 LUAD lines) |
| `has_expression_data` | boolean | RNA expression available (80/91) |
| `has_cn_data` | boolean | Copy number available (45/91) |

---

## Relationship Types

### Within-Pathway Gene Interactions
From KEGG individual pathway graphs. Carry `pathway_id` to identify which pathway context the interaction was observed in.

| Relationship | From → To | Properties | KEGG source |
|---|---|---|---|
| `ACTIVATES` | Gene → Gene | `pathway_id`, `subtype`, `indirect` | PPrel: activation |
| `INHIBITS` | Gene → Gene | `pathway_id`, `subtype`, `indirect` | PPrel: inhibition |
| `PHOSPHORYLATES` | Gene → Gene | `pathway_id` | PPrel: phosphorylation |
| `DEPHOSPHORYLATES` | Gene → Gene | `pathway_id` | PPrel: dephosphorylation |
| `BINDS` | Gene → Gene | `pathway_id` | PPrel: binding/association |
| `UBIQUITINATES` | Gene → Gene | `pathway_id` | PPrel: ubiquitination |
| `METHYLATES` | Gene → Gene | `pathway_id` | PPrel: methylation |
| `REGULATES_EXPRESSION_OF` | Gene → Gene | `pathway_id`, `direction` | GErel |
| `BINDS_COMPOUND` | Gene → Compound | `pathway_id` | PCrel |
| `COMPONENT_OF` | Gene → Gene | `pathway_id` | component_of (complex membership) |
| `PARTICIPATES_IN` | Gene → Pathway | `pathway_id` | gene appears in pathway |

---

### Pathway-Level Relationships
From `lung_cancer_pathways_graph.json`. Encode LUAD-specific pathway cross-talk derived from DEG overlap and SPIA analysis.

| Relationship | From → To | Properties | Meaning |
|---|---|---|---|
| `ACTIVATES_PATHWAY` | Pathway → Pathway | `edge_id`, `shared_genes`, `gene_ids`, `description` | Pathway A promotes activation of B |
| `REPRESSES_PATHWAY` | Pathway → Pathway | `edge_id`, `shared_genes`, `gene_ids`, `description` | Pathway A suppresses B |
| `SHARES_DEG_WITH` | Pathway → Pathway | `edge_id`, `shared_genes`, `gene_ids`, `description` | Pathways share differentially expressed genes |
| `DOWNSTREAM_OF` | Pathway → Pathway | `edge_id`, `shared_genes`, `gene_ids`, `description` | B is downstream of A |
| `CROSSTALK_WITH` | Pathway → Pathway | `edge_id`, `shared_genes`, `gene_ids`, `description` | Bidirectional regulatory crosstalk |

---

### Perturbation Layer Relationships
From `luad_perturbation_layer.json`. Encode the mutation → gene → pathway causal inference chain.

| Relationship | From → To | Key Properties | Meaning |
|---|---|---|---|
| `MUTATES` | Mutation → Gene | `effect_direction`, `luad_prevalence` | Mutation alters gene function |
| `MEMBER_OF` | Gene → Pathway | — | Gene is a key member of pathway |
| `PERTURBS` | Mutation → Pathway | `effect_direction`, `luad_prevalence`, `via_gene`, `mean_crispr_effect`, `is_gene_essential` | Shortcut: mutation causally perturbs pathway (through gene membership) |
| `CRISPR_VALIDATES` | Gene → Pathway | `mean_crispr_effect`, `mean_dep_prob`, `is_essential` | CRISPR data confirms gene's functional role in pathway in LUAD |

---

### Drug Relationships *(scaffold — populate from DrugBank/OpenTargets)*

| Relationship | From → To | Properties | Meaning |
|---|---|---|---|
| `TARGETS` | Drug → Gene | `mechanism`, `affinity_nm`, `source` | Drug's molecular target |
| `INHIBITS_PATHWAY` | Drug → Pathway | `evidence`, `source` | Drug suppresses a pathway |
| `SENSITIZES_TO` | Mutation → Drug | `evidence`, `source` | Mutation makes tumor sensitive to drug |
| `CONFERS_RESISTANCE_TO` | Mutation → Drug | `mechanism`, `evidence` | Mutation drives drug resistance |
| `SYNERGIZES_WITH` | Drug → Drug | `evidence`, `context` | Drug combination synergy |

---

### Cell Line / Disease Relationships

| Relationship | From → To | Meaning |
|---|---|---|
| `HAS_MUTATION` | CellLine → Mutation | Cell line carries this mutation |
| `MODELS` | CellLine → Disease | Cell line is a model of this disease |

---

## Causal Reasoning Traversal Patterns

These Cypher patterns are the core reasoning primitives for LLM query planning.

### P1 — Find all pathways activated by a mutation set
```cypher
MATCH (m:Mutation)-[:PERTURBS]->(p:Pathway)
WHERE m.id IN $mutation_ids
  AND m.effect_direction = "gain_of_function"
RETURN DISTINCT p.label, p.inferred_state, p.n_essential_genes_luad
ORDER BY p.n_essential_genes_luad DESC
```

### P2 — Identify synthetic lethal targets in an activated pathway
```cypher
MATCH (p:Pathway {inferred_state: "activated"})
MATCH (g:Gene)-[:MEMBER_OF]->(p)
WHERE g.is_essential_luad = true
  AND g.mean_crispr_effect_luad < -0.5
RETURN g.symbol, g.mean_dep_prob_luad, g.mean_crispr_effect_luad, p.label
ORDER BY g.mean_dep_prob_luad DESC
```

### P3 — Trace downstream compensation after pathway inhibition
```cypher
MATCH (target:Pathway {kegg_id: $inhibited_pathway})
MATCH (target)-[:SHARES_DEG_WITH|DOWNSTREAM_OF]->(downstream:Pathway)
MATCH (bypass:Pathway)-[:ACTIVATES_PATHWAY]->(downstream)
WHERE bypass <> target AND bypass.inferred_state = "activated"
RETURN bypass.label AS compensatory_pathway,
       downstream.label AS convergence_point
```

### P4 — Gene-level signal flow from driver mutation
```cypher
MATCH (m:Mutation {id: $mutation_id})-[:MUTATES]->(driver:Gene)
MATCH (driver)-[:ACTIVATES|PHOSPHORYLATES*1..4]->(effector:Gene)
WHERE effector.is_essential_luad = true
RETURN driver.symbol, effector.symbol,
       effector.mean_dep_prob_luad AS dependency
ORDER BY effector.mean_dep_prob_luad DESC
```

### P5 — Resistance mechanism: causal path through pathway graph
```cypher
MATCH (m:Mutation)-[:PERTURBS]->(p1:Pathway)
MATCH path = (p1)-[:ACTIVATES_PATHWAY|DOWNSTREAM_OF*1..3]->(p2:Pathway)
OPTIONAL MATCH (p2)-[:REPRESSES_PATHWAY]->(suppressed:Pathway)
RETURN m.label, p1.label,
       [n IN nodes(path) | n.label] AS causal_chain,
       suppressed.label AS suppressed_pathway
ORDER BY length(path)
```

### P6 — Context window: full subgraph for a clinical case
```cypher
MATCH (m:Mutation)
WHERE m.id IN $active_mutations
MATCH (m)-[:PERTURBS]->(p:Pathway)
OPTIONAL MATCH (p)-[pw_rel:ACTIVATES_PATHWAY|REPRESSES_PATHWAY|
                    DOWNSTREAM_OF|SHARES_DEG_WITH]->(p2:Pathway)
OPTIONAL MATCH (g:Gene)-[:MEMBER_OF]->(p)
WHERE g.is_essential_luad = true
OPTIONAL MATCH (d:Drug)-[:TARGETS]->(g)
RETURN m, p, pw_rel, p2, g, d
LIMIT 250
```

---

## Integration Key: How Sources Merge

| Entity | Merge key | KEGG entry | lung_cancer_graph | perturbation_layer |
|--------|-----------|-----------|-------------------|-------------------|
| Gene | `symbol` | label field (first symbol before comma) | `key_genes[]` strings | `gene_nodes[].symbol` |
| Pathway | `kegg_id` | `pathway_id` in meta | `kegg_id` field | `kegg_id` field on pathway_nodes |
| Mutation | `id` | — | — | `mutation_nodes[].id` |

Gene KEGG entries with `type="gene"` resolve to Gene nodes via the label field (e.g. `"KRAS, RASK2, NS3..."` → symbol `"KRAS"`).
Gene entries with multiple KEGG IDs (`name = "hsa:3845 hsa:4893"`) produce one Gene node per HGNC symbol, linked by ACTIVATES/INHIBITS relationships that share a `pathway_id`.
KEGG entries with `type="map"` resolve to Pathway nodes via the `name` field (e.g. `"path:hsa04010"` → `kegg_id = "hsa04010"`).

---

## Schema Version

- **Schema version:** 1.0
- **KEGG pathways loaded:** hsa01521, hsa04010, hsa04012, hsa04014, hsa04068, hsa04115, hsa04150, hsa04151
- **LUAD cell lines:** 91 (OncotreeCode = LUAD, DepMap 24Q4)
- **Perturbation layer context:** LUAD, n=91 cell lines
