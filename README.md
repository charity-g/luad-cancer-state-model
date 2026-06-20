# Causal Biological Reasoning System

## Graph-Native LLM Architecture for Intervention Prediction and Clinical Simulation

---

# 1. Project Overview

This project simulates a biologically grounded causal reasoning system inspired by PDGrapher, but implemented using:

* Graph databases
* Large Language Models (LLMs)
* Causal inference systems
* Biological knowledge graphs
* Drug and perturbation databases

The system is designed to answer questions such as:

* What is the survivability of a tumor under specific drug combinations?
* Which intervention is most likely to suppress a resistant tumor state?
* What compensatory pathways emerge after inhibition?
* Which perturbations reverse a disease phenotype?
* What causal mechanisms explain observed resistance?

The architecture prioritizes:

* Explicit causality
* Explainability
* Biological fidelity
* Context-aware reasoning
* Natural language accessibility

---

# 2. Core System Philosophy

Unlike pure neural-network approaches, this framework represents biology as an explicit causal graph.

The graph acts as a structured world model of biological systems.

LLMs operate as:

* translators,
* orchestrators,
* hypothesis generators,
* and explanation engines.

The causal engine performs:

* intervention simulation,
* treatment effect estimation,
* counterfactual reasoning,
* and state-transition prediction.

---

# 3. High-Level Architecture

```text
User Prompt
    ↓
LLM Translation Layer
    ↓
Graph Query Generation
    ↓
Fact-Rich Biological Subgraph Retrieval
    ↓
Causal Inference + Simulation Engine
    ↓
LLM Synthesis Layer
    ↓
Final Response
```

---

# 4. Possible Architectures

## Architecture A — Retrieval + Reasoning Pipeline

```text
User Prompt
    ↓
LLM → Cypher Translation
    ↓
Neo4j Query
    ↓
Subgraph Extraction
    ↓
Causal Analysis
    ↓
LLM Explanation
```

Use Cases:

* Treatment recommendation
* Mechanistic explanations
* Drug resistance analysis

Advantages:

* Simple
* Explainable
* Fast iteration

Limitations:

* Less adaptive
* Limited temporal reasoning

---

## Architecture B — Dynamic State Transition System

```text
Current Biological State
    ↓
Apply Intervention
    ↓
Predict State Transition
    ↓
Generate New State Graph
    ↓
Evaluate Survival / Resistance
```

Use Cases:

* Adaptive resistance
* Time-series simulations
* Evolutionary trajectories

Advantages:

* Better biological realism
* Captures compensatory rewiring

Limitations:

* More computationally expensive

---

## Architecture C — Agentic Multi-Step Reasoning

```text
Planner Agent
    ↓
Query Agent
    ↓
Causal Engine
    ↓
Simulation Agent
    ↓
Explanation Agent
```

Each agent has specialized responsibilities.

Advantages:

* Modular
* Extensible
* Easier debugging

Potential agents:

* Drug agent
* Mutation agent
* Pathway agent
* Survival estimator
* Resistance predictor

---

# 5. Translation Layer

## Purpose

The translation layer converts natural language into structured biological reasoning tasks.

It acts as:

* semantic parser,
* biological interpreter,
* query planner,
* and reasoning orchestrator.

---

## Translation Layer Responsibilities

### 1. Clinical Context Extraction

Extract:

* mutations,
* tumor type,
* treatment history,
* biomarkers,
* resistance states,
* prior perturbations.

Example:

Input:

```text
KRAS G12C LUAD resistant to osimertinib with STK11 loss
```

Structured state:

```json
{
  "disease": "LUAD",
  "mutations": ["KRAS_G12C", "STK11_LOSS"],
  "drug_resistance": ["osimertinib"]
}
```

---

### 2. Graph Database Access

The translator can access:

* Graph database
* Perturbation databases
* Drug databases
* Pathway databases
* Omics embeddings
* Experimental evidence stores

Examples:

* Neo4j
* Hetionet
* OpenTargets
* DrugBank
* LINCS
* DepMap
* TCGA
* Reactome

---

### 3. Query Planning

The LLM determines:

* which graph regions matter,
* which interventions are relevant,
* what evidence thresholds to use,
* what causal paths to explore.

Example:

```cypher
MATCH (m:Mutation)-[:ACTIVATES]->(p:Pathway)
WHERE m.name = "KRAS_G12C"
RETURN p
```

---

### 4. Perturbation Reasoning

The translation layer can reason over:

* CRISPR perturbations,
* knockouts,
* drug combinations,
* pathway inhibition,
* synthetic lethality.

---

# 6. Graph Database Layer

## Core Concept

The graph is the biological memory system.

Nodes represent entities.
Edges represent causal or biological relationships.

---

## Node Types

### Biological Entities

```text
Gene
Protein
Pathway
Mutation
Disease
CellState
TumorState
Drug
Perturbation
Biomarker
PatientContext
```

---

## State Nodes

State nodes represent biological contexts.

Example:

```json
{
  "KRAS": "mutated",
  "STK11": "loss",
  "ERK_activity": "high",
  "PDL1": "upregulated"
}
```

These become graph-native latent states.

---

## Intervention Nodes

Represent:

* drug administration,
* gene knockout,
* pathway inhibition,
* combinatorial therapy.

---

## Edge Types

```text
CAUSES
INHIBITS
ACTIVATES
SUPPRESSES
UPREGULATES
DOWNREGULATES
SENSITIZES
CONFERS_RESISTANCE
SYNERGIZES_WITH
```

Edges contain:

* confidence
* evidence
* context
* publication references
* experimental conditions

Example:

```cypher
CREATE (kras)-[:CAUSES {
    strength: 0.89,
    confidence: 0.95,
    context: "LUAD"
}]->(erk)
```

---

# 7. Causal Inference Engine

## Purpose

Provides mathematical reasoning over interventions.

This is the simulation core.

---

## Core Capabilities

### 1. Structural Causal Models (SCMs)

Implements:

* Pearl do-calculus
* intervention semantics
* causal propagation

Example:

```text
do(MEK_inhibition)
→ downstream ERK suppression
→ altered survival probability
```

---

### 2. Conditional Average Treatment Effect (CATE)

Predict treatment effects conditioned on context.

Example:

```text
Effect of KRAS inhibitor
given:
- STK11 loss
- TP53 WT
- high MAPK signaling
```

---

### 3. Counterfactual Reasoning

Answer:

```text
What if the patient had received SHP2 inhibition earlier?
```

---

### 4. State Transition Prediction

Predict:

* resistance evolution,
* compensatory rewiring,
* phenotypic adaptation,
* tumor escape mechanisms.

---

# 8. LLM Reasoning Layer

## Role of the LLM

The LLM is NOT the source of truth.

The graph is the source of truth.

The LLM performs:

* translation,
* orchestration,
* explanation,
* summarization,
* hypothesis generation.

---

## LLM Functions

### Natural Language → Query Translation

Example:

```text
Which interventions reverse KRAS-driven MAPK signaling?
```

↓

Cypher + causal plan.

---

### Mechanistic Explanation

Generate clinician-readable explanations.

Example:

```text
MEK inhibition alone is predicted to fail due to compensatory PI3K activation mediated by STK11 loss.
```

---

### Hypothesis Generation

The LLM can propose:

* missing causal edges,
* novel intervention combinations,
* synthetic lethal relationships.

---

### Query Optimization

The LLM determines:

* graph traversal depth,
* evidence weighting,
* relevant subgraph boundaries.

---

# 9. Fact-Rich Subgraph Retrieval

## Objective

Extract biologically relevant causal neighborhoods.

The subgraph becomes the reasoning context window.

---

## Retrieval Pipeline

```text
Clinical Context
    ↓
Entity Extraction
    ↓
Neighborhood Expansion
    ↓
Pathway Prioritization
    ↓
Evidence Filtering
    ↓
Subgraph Compression
```

---

## Retrieval Constraints

Subgraphs may be filtered by:

* tissue type,
* mutation context,
* evidence quality,
* temporal relevance,
* experimental system,
* species.

---

# 10. Example End-to-End Query

## User Question

```text
What interventions would be effective for a KRAS G12C LUAD tumor with STK11 loss resistant to osimertinib?
```

---

## Pipeline

### Step 1 — Parse Context

Extract:

* KRAS_G12C
* STK11 loss
* LUAD
* osimertinib resistance

---

### Step 2 — Retrieve Subgraph

Retrieve:

* MAPK pathway
* PI3K pathway
* resistance mechanisms
* known combination therapies
* synthetic lethal partners

---

### Step 3 — Causal Simulation

Evaluate:

* MEK inhibition
* SHP2 inhibition
* KRAS inhibitor combinations
* immune sensitization

---

### Step 4 — Rank Interventions

Estimate:

* tumor suppression probability
* resistance likelihood
* pathway compensation risk

---

### Step 5 — Generate Explanation

Example:

```text
Dual SHP2 + KRAS inhibition is predicted to outperform MEK inhibition due to adaptive ERK reactivation observed in STK11-deficient tumors.
```

---

# 11. Advantages Over Pure Neural Networks

## Explicit Causality

Relationships are visible and inspectable.

---

## Interpretability

Predictions can be traced through evidence paths.

---

## Biological Fidelity

State transitions match biological systems more closely than static embeddings.

---

## Flexible Integration

New data sources can be added without retraining the entire model.

---

## Clinician Accessibility

Natural language interface.

---

## Hybrid Intelligence

Combines:

* symbolic reasoning,
* statistical inference,
* graph traversal,
* and LLM synthesis.

---

# 12. Future Extensions

## Multi-Omics Integration

Add:

* transcriptomics,
* phosphoproteomics,
* metabolomics,
* spatial omics.

---

## Temporal Graphs

Model:

* longitudinal treatment trajectories,
* tumor evolution,
* adaptive resistance.

---

## Reinforcement Learning Layer

Optimize:

* treatment sequencing,
* adaptive therapies,
* intervention timing.

---

## Graph Neural Networks

Use GNNs for:

* embedding generation,
* pattern discovery,
* latent structure learning.

---

# 13. Recommended Technology Stack

## Graph Layer

* Neo4j
* Memgraph
* TigerGraph

---

## LLM Layer

* GPT models
* Claude
* open-source reasoning models

---

## Causal Inference

* DoWhy
* EconML
* PyWhy
* causal-learn

---

## Biological Data

* DrugBank
* OpenTargets
* Reactome
* LINCS
* DepMap
* TCGA
* Hetionet

---

# 14. System Design Principles

1. Graph is source of truth.
2. LLM performs orchestration, not factual storage.
3. Causal semantics must remain explicit.
4. Every prediction should be explainable.
5. Biological context is mandatory.
6. State transitions are first-class objects.
7. Intervention reasoning must support counterfactuals.
8. Retrieval should prioritize mechanistic relevance over embedding similarity.

---

# 15. Vision

The long-term goal is a biologically grounded causal reasoning engine capable of:

* intervention simulation,
* mechanistic reasoning,
* resistance prediction,
* therapy optimization,
* and scientific hypothesis generation.

The system bridges:

* symbolic AI,
* causal inference,
* graph databases,
* and large language models

to create an interpretable biological intelligence framework.
