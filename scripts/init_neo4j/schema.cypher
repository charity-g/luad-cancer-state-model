// =============================================================================
// Neo4j Schema — LUAD Causal Biological Reasoning System
// =============================================================================
// Sources integrated:
//   1. KEGG individual pathway graphs  (hsa01521, hsa04010, hsa04012, hsa04014,
//                                       hsa04068, hsa04115, hsa04150, hsa04151)
//   2. lung_cancer_pathways_graph.json  (pathway-level DEG + crosstalk graph)
//   3. luad_perturbation_layer.json     (mutation → gene → pathway causal layer)
//
// Reasoning targets:
//   Q1. Tumor survivability under drug combinations
//   Q2. Intervention to suppress resistant tumor state
//   Q3. Compensatory pathways after inhibition
//   Q4. Perturbations that reverse disease phenotype
//   Q5. Causal mechanisms of resistance
// =============================================================================


// -----------------------------------------------------------------------------
// SECTION 1 — CONSTRAINTS  (uniqueness + existence)
// -----------------------------------------------------------------------------

// Gene — primary key is HGNC symbol
CREATE CONSTRAINT gene_symbol_unique IF NOT EXISTS
  FOR (g:Gene) REQUIRE g.symbol IS UNIQUE;

// Pathway — primary key is KEGG pathway ID (e.g. "hsa04010")
CREATE CONSTRAINT pathway_kegg_id_unique IF NOT EXISTS
  FOR (p:Pathway) REQUIRE p.kegg_id IS UNIQUE;

// Mutation
CREATE CONSTRAINT mutation_id_unique IF NOT EXISTS
  FOR (m:Mutation) REQUIRE m.id IS UNIQUE;

// Compound (KEGG chemical)
CREATE CONSTRAINT compound_id_unique IF NOT EXISTS
  FOR (c:Compound) REQUIRE c.id IS UNIQUE;

// Drug (scaffold for DrugBank / OpenTargets integration)
CREATE CONSTRAINT drug_id_unique IF NOT EXISTS
  FOR (d:Drug) REQUIRE d.id IS UNIQUE;

// Disease
CREATE CONSTRAINT disease_id_unique IF NOT EXISTS
  FOR (dis:Disease) REQUIRE dis.id IS UNIQUE;

// CellLine
CREATE CONSTRAINT cellline_model_id_unique IF NOT EXISTS
  FOR (cl:CellLine) REQUIRE cl.model_id IS UNIQUE;


// -----------------------------------------------------------------------------
// SECTION 2 — INDEXES
// -----------------------------------------------------------------------------

// Gene lookups
CREATE INDEX gene_entrez_id IF NOT EXISTS FOR (g:Gene) ON (g.entrez_id);
CREATE INDEX gene_is_essential IF NOT EXISTS FOR (g:Gene) ON (g.is_essential_luad);
CREATE INDEX gene_crispr_effect IF NOT EXISTS FOR (g:Gene) ON (g.mean_crispr_effect_luad);
CREATE INDEX gene_dep_prob IF NOT EXISTS FOR (g:Gene) ON (g.mean_dep_prob_luad);

// Pathway lookups
CREATE INDEX pathway_status IF NOT EXISTS FOR (p:Pathway) ON (p.status);
CREATE INDEX pathway_inferred_state IF NOT EXISTS FOR (p:Pathway) ON (p.inferred_state);
CREATE INDEX pathway_deg_count IF NOT EXISTS FOR (p:Pathway) ON (p.deg_count);

// Mutation lookups
CREATE INDEX mutation_class IF NOT EXISTS FOR (m:Mutation) ON (m.mutation_class);
CREATE INDEX mutation_effect_dir IF NOT EXISTS FOR (m:Mutation) ON (m.effect_direction);
CREATE INDEX mutation_prevalence IF NOT EXISTS FOR (m:Mutation) ON (m.luad_prevalence);
CREATE INDEX mutation_gene IF NOT EXISTS FOR (m:Mutation) ON (m.gene_symbol);

// Drug lookups
CREATE INDEX drug_name IF NOT EXISTS FOR (d:Drug) ON (d.name);
CREATE INDEX drug_class IF NOT EXISTS FOR (d:Drug) ON (d.drug_class);

// Full-text search (natural language → entity lookup)
CREATE FULLTEXT INDEX gene_text_search IF NOT EXISTS
  FOR (g:Gene) ON EACH [g.symbol, g.name_aliases];

CREATE FULLTEXT INDEX pathway_text_search IF NOT EXISTS
  FOR (p:Pathway) ON EACH [p.label, p.title, p.description];

CREATE FULLTEXT INDEX mutation_text_search IF NOT EXISTS
  FOR (m:Mutation) ON EACH [m.label, m.gene_symbol];

CREATE FULLTEXT INDEX drug_text_search IF NOT EXISTS
  FOR (d:Drug) ON EACH [d.name, d.drug_class, d.mechanism];


// -----------------------------------------------------------------------------
// SECTION 3 — NODE SCHEMAS  (MERGE templates; used by upload_init.py)
// -----------------------------------------------------------------------------

// --- 3a. Gene ---
// Sources: KEGG pathway entry nodes (type=gene) + perturbation layer gene_nodes
// Merge key: symbol
//
// MERGE (g:Gene {symbol: $symbol})
// SET g += {
//   entrez_id:                 $entrez_id,          // integer; NCBI Entrez
//   kegg_ids:                  $kegg_ids,            // string[] e.g. ["hsa:3845"]
//   name_aliases:              $name_aliases,        // string[] from KEGG label field
//   // DepMap LUAD aggregates (from perturbation layer):
//   mean_crispr_effect_luad:   $mean_crispr_effect_luad,   // float; Chronos score
//   std_crispr_effect_luad:    $std_crispr_effect_luad,
//   n_luad_crispr_measured:    $n_luad_crispr_measured,    // int; # cell lines with data
//   mean_dep_prob_luad:        $mean_dep_prob_luad,        // float; 0-1
//   is_essential_luad:         $is_essential_luad,         // bool; dep_prob > 0.5
//   mean_expression_luad:      $mean_expression_luad,      // float; log(TPM+1)
//   std_expression_luad:       $std_expression_luad,
//   mean_cn_luad:              $mean_cn_luad,              // float; copy number
//   cn_status_luad:            $cn_status_luad             // "neutral"|"amplified"|"deleted"
// }

// --- 3b. Pathway ---
// Sources: lung_cancer_pathways_graph + luad_perturbation_layer + KEGG map entries
// Merge key: kegg_id
//
// MERGE (p:Pathway {kegg_id: $kegg_id})
// SET p += {
//   id:                            $id,              // snake_case e.g. "MAPK_signaling"
//   label:                         $label,           // human-readable short name
//   title:                         $title,           // KEGG verbose title
//   // DEG statistics (from lung_cancer_pathways_graph):
//   status:                        $status,          // "activated"|"repressed"|"crosstalk_hub"|"nsclc_enriched"
//   q_value:                       $q_value,         // float
//   deg_count:                     $deg_count,       // int
//   upregulated_degs:              $upregulated_degs,
//   downregulated_degs:            $downregulated_degs,
//   impact_factor:                 $impact_factor,   // float; SPIA score
//   description:                   $description,
//   // DepMap augmentation (from perturbation layer):
//   mean_pathway_crispr_effect_luad: $mean_pathway_crispr_effect_luad,
//   n_essential_genes_luad:          $n_essential_genes_luad,
//   inferred_state:                  $inferred_state, // "activated"|"repressed"|"ambiguous"
//   perturbation_sources:            $perturbation_sources, // string[] mutation ids
//   // KEGG graph metadata:
//   node_count:                    $node_count,
//   edge_count:                    $edge_count,
//   kgml_url:                      $kgml_url
// }

// --- 3c. Mutation ---
// Source: luad_perturbation_layer mutation_nodes
// Merge key: id
//
// MERGE (m:Mutation {id: $id})
// SET m += {
//   label:            $label,           // e.g. "KRAS p.G12C"
//   mutation_class:   $mutation_class,  // "hotspot"|"lof"|"fusion"|"msi"
//   effect_direction: $effect_direction,// "gain_of_function"|"loss_of_function"|"ambiguous"
//   gene_symbol:      $gene_symbol,     // HGNC symbol of affected gene
//   luad_prevalence:  $luad_prevalence, // float 0-1; fraction of LUAD lines positive
//   luad_n_positive:  $luad_n_positive, // int
//   luad_n_total:     $luad_n_total     // int
// }

// --- 3d. Compound ---
// Source: KEGG pathway entry nodes (type=compound)
// Merge key: id (KEGG compound ID e.g. "C00338")
//
// MERGE (c:Compound {id: $id})
// SET c += {
//   name:     $name,
//   kegg_id:  $kegg_id,
//   link:     $link
// }

// --- 3e. Drug  (scaffold — populated from DrugBank / OpenTargets) ---
// Merge key: id
//
// MERGE (d:Drug {id: $id})
// SET d += {
//   name:        $name,
//   drug_class:  $drug_class,    // "TKI"|"MEKi"|"mTORi"|"immunotherapy" etc.
//   mechanism:   $mechanism,     // "competitive inhibitor"|"allosteric" etc.
//   fda_status:  $fda_status,    // "approved"|"investigational"
//   targets:     $targets        // string[] gene symbols (denormalized convenience copy)
// }

// --- 3f. Disease ---
// Merge key: id
//
// MERGE (dis:Disease {id: $id})
// SET dis += {
//   name:             $name,            // "Lung Adenocarcinoma"
//   oncotree_code:    $oncotree_code,   // "LUAD"
//   oncotree_lineage: $oncotree_lineage // "Lung"
// }

// --- 3g. CellLine ---
// Source: DepMap Model.csv filtered to LUAD
// Merge key: model_id
//
// MERGE (cl:CellLine {model_id: $model_id})
// SET cl += {
//   name:                  $name,
//   sex:                   $sex,
//   age:                   $age,
//   primary_or_metastatic: $primary_or_metastatic,
//   collection_site:       $collection_site,
//   has_crispr_data:       $has_crispr_data,   // bool
//   has_expression_data:   $has_expression_data,
//   has_cn_data:           $has_cn_data
// }


// -----------------------------------------------------------------------------
// SECTION 4 — RELATIONSHIP TYPES
// -----------------------------------------------------------------------------
//
// Convention: all relationship types UPPER_SNAKE_CASE.
// Direction encodes causal flow where meaningful.
//
// ── WITHIN-PATHWAY GENE INTERACTIONS  (from KEGG individual pathway graphs) ──
//
//   (:Gene)-[:ACTIVATES {
//     pathway_id:   string,  // e.g. "hsa04010" — which pathway this edge comes from
//     subtype:      string,  // "activation"|"phosphorylation"|"indirect effect"
//     source:       "kegg"
//   }]->(:Gene)
//
//   (:Gene)-[:INHIBITS {
//     pathway_id:   string,
//     subtype:      string,  // "inhibition"|"dephosphorylation"
//     source:       "kegg"
//   }]->(:Gene)
//
//   (:Gene)-[:PHOSPHORYLATES {
//     pathway_id:   string,
//     source:       "kegg"
//   }]->(:Gene)
//
//   (:Gene)-[:DEPHOSPHORYLATES {pathway_id, source}]->(:Gene)
//
//   (:Gene)-[:BINDS {
//     pathway_id:   string,
//     source:       "kegg"
//   }]->(:Gene)
//
//   (:Gene)-[:UBIQUITINATES {pathway_id, source}]->(:Gene)
//   (:Gene)-[:METHYLATES {pathway_id, source}]->(:Gene)
//
//   (:Gene)-[:REGULATES_EXPRESSION_OF {
//     pathway_id:  string,
//     direction:   string,  // "expression" (GErel)
//     source:      "kegg"
//   }]->(:Gene)
//
//   (:Gene)-[:BINDS_COMPOUND {
//     pathway_id:  string,
//     source:      "kegg"
//   }]->(:Compound)
//
//   (:Gene)-[:COMPONENT_OF {
//     pathway_id:  string    // gene is part of a complex/group in this pathway
//   }]->(:Gene)             // target = the representative/anchor gene of the group
//
//   (:Gene)-[:PARTICIPATES_IN {
//     pathway_id:  string    // gene appears in this KEGG pathway
//   }]->(:Pathway)
//
//
// ── PATHWAY-LEVEL RELATIONSHIPS  (from lung_cancer_pathways_graph) ─────────
//
//   (:Pathway)-[:ACTIVATES_PATHWAY {
//     edge_id:      string,
//     shared_genes: string[],
//     gene_ids:     integer[],
//     description:  string,
//     source:       "lung_cancer_graph"
//   }]->(:Pathway)
//
//   (:Pathway)-[:REPRESSES_PATHWAY {
//     edge_id, shared_genes, gene_ids, description, source
//   }]->(:Pathway)
//
//   (:Pathway)-[:SHARES_DEG_WITH {
//     edge_id:      string,
//     shared_genes: string[],
//     gene_ids:     integer[],
//     description:  string,
//     source:       "lung_cancer_graph"
//   }]->(:Pathway)
//
//   (:Pathway)-[:DOWNSTREAM_OF {
//     edge_id, shared_genes, gene_ids, description, source
//   }]->(:Pathway)
//
//   (:Pathway)-[:CROSSTALK_WITH {
//     edge_id, shared_genes, gene_ids, description, source
//   }]->(:Pathway)
//
//
// ── PERTURBATION LAYER  (from luad_perturbation_layer) ────────────────────
//
//   (:Mutation)-[:MUTATES {
//     edge_id:          string,
//     effect_direction: string,   // "gain_of_function"|"loss_of_function"
//     luad_prevalence:  float,
//     description:      string,
//     source:           "depmap"
//   }]->(:Gene)
//
//   (:Gene)-[:MEMBER_OF {
//     edge_id: string,
//     source:  "lung_cancer_graph"
//   }]->(:Pathway)
//
//   (:Mutation)-[:PERTURBS {
//     edge_id:              string,
//     effect_direction:     string,
//     luad_prevalence:      float,
//     via_gene:             string,   // gene symbol shortcut
//     mean_crispr_effect:   float,
//     is_gene_essential:    boolean,
//     description:          string,
//     source:               "depmap"
//   }]->(:Pathway)
//
//   (:Gene)-[:CRISPR_VALIDATES {
//     edge_id:            string,
//     mean_crispr_effect: float,   // Chronos score; more negative = more essential
//     mean_dep_prob:      float,
//     is_essential:       boolean,
//     source:             "depmap"
//   }]->(:Pathway)
//
//
// ── DRUG RELATIONSHIPS  (scaffold for DrugBank / OpenTargets) ────────────
//
//   (:Drug)-[:TARGETS {
//     mechanism:     string,   // "ATP competitive inhibitor"
//     affinity_nm:   float,    // binding affinity if known
//     source:        string    // "drugbank"|"opentargets"
//   }]->(:Gene)
//
//   (:Drug)-[:INHIBITS_PATHWAY {
//     evidence:   string,
//     source:     string
//   }]->(:Pathway)
//
//   (:Mutation)-[:SENSITIZES_TO {
//     // mutation makes tumor sensitive to this drug
//     evidence:   string,
//     source:     string
//   }]->(:Drug)
//
//   (:Mutation)-[:CONFERS_RESISTANCE_TO {
//     mechanism:  string,
//     evidence:   string,
//     source:     string
//   }]->(:Drug)
//
//   (:Drug)-[:SYNERGIZES_WITH {
//     evidence:   string,
//     context:    string   // e.g. "KRAS_G12C LUAD"
//   }]->(:Drug)
//
//
// ── CELL LINE RELATIONSHIPS  (DepMap context) ────────────────────────────
//
//   (:CellLine)-[:HAS_MUTATION]->(:Mutation)
//   (:CellLine)-[:MODELS]->(:Disease)


// -----------------------------------------------------------------------------
// SECTION 5 — EXAMPLE CYPHER QUERIES FOR LLM REASONING
// -----------------------------------------------------------------------------

// ── Q1. Survivability: which pathways remain active after dual drug inhibition?
//
// MATCH (d:Drug)-[:TARGETS]->(g:Gene)-[:MEMBER_OF]->(targeted:Pathway)
// WHERE d.name IN ["osimertinib", "trametinib"]
// WITH collect(distinct targeted.kegg_id) AS hit_pathways
// MATCH (bypass:Pathway)
// WHERE NOT bypass.kegg_id IN hit_pathways
//   AND bypass.inferred_state = "activated"
// OPTIONAL MATCH (targeted_p:Pathway)-[:SHARES_DEG_WITH|ACTIVATES_PATHWAY]->(bypass)
// WHERE targeted_p.kegg_id IN hit_pathways
// RETURN bypass.label                       AS compensatory_pathway,
//        bypass.n_essential_genes_luad      AS essential_genes,
//        bypass.mean_pathway_crispr_effect_luad AS crispr_vulnerability,
//        count(targeted_p)                  AS upstream_connections
// ORDER BY upstream_connections DESC, crispr_vulnerability ASC;


// ── Q2. Which gene knockouts suppress a resistant KRAS G12C tumor?
//
// MATCH (mut:Mutation {id: "mut_KRAS_p_G12C"})-[:PERTURBS]->(p:Pathway)
// WHERE p.inferred_state IN ["activated", "ambiguous"]
// MATCH (g:Gene)-[:MEMBER_OF]->(p)
// WHERE g.is_essential_luad = true
//   AND g.mean_crispr_effect_luad < -0.5
//   AND g.symbol <> "KRAS"               // exclude driver itself
// RETURN g.symbol                        AS synthetic_lethal_target,
//        g.mean_crispr_effect_luad       AS crispr_effect,
//        g.mean_dep_prob_luad            AS dependency_probability,
//        p.label                         AS affected_pathway
// ORDER BY g.mean_dep_prob_luad DESC;


// ── Q3. Compensatory pathway rewiring after MEK inhibition
//
// MATCH (mek_pathway:Pathway {kegg_id: "hsa04010"})
// MATCH (mek_pathway)-[:SHARES_DEG_WITH|DOWNSTREAM_OF]->(downstream:Pathway)
// MATCH (alt:Pathway)-[:ACTIVATES_PATHWAY]->(downstream)
// WHERE alt <> mek_pathway
//   AND alt.inferred_state = "activated"
// RETURN alt.label                         AS compensatory_pathway,
//        downstream.label                  AS converges_on,
//        alt.mean_pathway_crispr_effect_luad AS crispr_vulnerability
// ORDER BY alt.mean_pathway_crispr_effect_luad ASC;


// ── Q4. Which CRISPR perturbations reverse the LUAD disease phenotype?
//
// MATCH (p:Pathway)
// WHERE p.inferred_state = "activated"
// MATCH (g:Gene)-[:MEMBER_OF]->(p)
// WHERE g.is_essential_luad = true
//   AND g.mean_crispr_effect_luad < -0.5
// OPTIONAL MATCH (mut:Mutation)-[:MUTATES]->(g)
// RETURN g.symbol                        AS reversal_target,
//        g.mean_crispr_effect_luad       AS essentiality_score,
//        g.mean_dep_prob_luad            AS dependency_prob,
//        p.label                         AS oncogenic_pathway,
//        collect(mut.label)              AS known_activating_mutations
// ORDER BY g.mean_crispr_effect_luad ASC
// LIMIT 20;


// ── Q5. Causal chain: how does TP53 loss lead to resistance?
//
// MATCH (tp53:Mutation {id: "mut_TP53_LoF"})
// MATCH (tp53)-[:PERTURBS]->(p1:Pathway)
// MATCH path = (p1)-[:ACTIVATES_PATHWAY|DOWNSTREAM_OF*1..3]->(p2:Pathway)
// WHERE p1 <> p2
// OPTIONAL MATCH (p2)-[:REPRESSES_PATHWAY]->(p3:Pathway)
// RETURN tp53.label                         AS driver_mutation,
//        p1.label                           AS directly_perturbed,
//        [n IN nodes(path) | n.label]       AS causal_chain,
//        p3.label                           AS repressed_outcome
// ORDER BY length(path);


// ── Q6. Full context subgraph for a given mutation profile (LLM context window)
//
// MATCH (mut:Mutation)
// WHERE mut.id IN ["mut_KRAS_p_G12C", "mut_TP53_LoF", "mut_STK11_LoF"]
// MATCH (mut)-[:PERTURBS]->(p:Pathway)
// OPTIONAL MATCH (p)-[r:ACTIVATES_PATHWAY|REPRESSES_PATHWAY|DOWNSTREAM_OF|SHARES_DEG_WITH]->(p2:Pathway)
// OPTIONAL MATCH (g:Gene)-[:MEMBER_OF]->(p)
// WHERE g.is_essential_luad = true
// OPTIONAL MATCH (g)-[:ACTIVATES|INHIBITS]->(g2:Gene)
// WHERE g2.is_essential_luad = true
// RETURN mut, p, r, p2, g, g2
// LIMIT 200;


// -----------------------------------------------------------------------------
// SECTION 6 — RELATIONSHIP SUBTYPE → NEO4J RELATIONSHIP TYPE MAPPING
// -----------------------------------------------------------------------------
//
// KEGG PPrel subtypes map to Neo4j relationship types as follows:
//
//   "activation"          -> ACTIVATES
//   "inhibition"          -> INHIBITS
//   "phosphorylation"     -> PHOSPHORYLATES
//   "dephosphorylation"   -> DEPHOSPHORYLATES
//   "binding/association" -> BINDS
//   "ubiquitination"      -> UBIQUITINATES
//   "methylation"         -> METHYLATES
//   "indirect effect"     -> ACTIVATES / INHIBITS  (with indirect: true property)
//   "missing interaction" -> ACTIVATES / INHIBITS  (with missing: true property)
//
// KEGG GErel -> REGULATES_EXPRESSION_OF
// KEGG PCrel -> BINDS_COMPOUND
// KEGG component_of -> COMPONENT_OF
//
// lung_cancer_pathways_graph edge types map as:
//   "activates"     -> ACTIVATES_PATHWAY
//   "represses"     -> REPRESSES_PATHWAY
//   "shared_DEG"    -> SHARES_DEG_WITH
//   "downstream_of" -> DOWNSTREAM_OF
//   "crosstalk"     -> CROSSTALK_WITH
//
// perturbation layer edge types map as:
//   "mutates"          -> MUTATES
//   "member_of"        -> MEMBER_OF
//   "perturbs"         -> PERTURBS
//   "crispr_validates" -> CRISPR_VALIDATES


// -----------------------------------------------------------------------------
// SECTION 7 — GRAPH STATISTICS (after full load, for verification)
// -----------------------------------------------------------------------------

// MATCH (n) RETURN labels(n) AS label, count(*) AS count ORDER BY count DESC;
// MATCH ()-[r]->() RETURN type(r) AS rel_type, count(*) AS count ORDER BY count DESC;
//
// Expected node counts (approximate):
//   Gene      ~639  (unique after dedup across 8 KEGG graphs + perturbation layer)
//   Pathway   ~26   (lung_cancer_graph) + up to 79 map entries from KEGG graphs
//   Mutation  ~39   (from OmicsInferredMolecularSubtypes, LUAD)
//   Compound  ~38   (from KEGG individual graphs)
//   Disease   1     (LUAD)
//   CellLine  91    (DepMap LUAD)
//
// Expected relationship counts (approximate):
//   ACTIVATES / INHIBITS / PHOSPHORYLATES etc.  ~700+  (KEGG within-pathway)
//   REGULATES_EXPRESSION_OF                      ~83
//   BINDS_COMPOUND                               ~48
//   COMPONENT_OF                                 ~60
//   PARTICIPATES_IN                              ~639
//   MEMBER_OF                                    ~108
//   SHARES_DEG_WITH                              ~22
//   ACTIVATES_PATHWAY / REPRESSES_PATHWAY        ~4
//   DOWNSTREAM_OF                                ~7
//   CROSSTALK_WITH                               ~3
//   MUTATES                                      ~16
//   PERTURBS                                     ~37
//   CRISPR_VALIDATES                             ~101
