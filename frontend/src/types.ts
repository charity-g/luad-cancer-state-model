export type EffectType =
  | 'activating'
  | 'gain_of_function'
  | 'inactivating'
  | 'loss_of_function'
  | 'uncertain'
  | 'no_effect'

export interface ContextCard {
  id: string
  protein: string
  effect: EffectType
  mutation_id: string
  pathway?: string
  hgvs_protein?: string
}

export interface MutationFeatures {
  is_hotspot: boolean
  is_lof: boolean
  is_high_impact: boolean
  oncogene_high_impact: boolean
  tsg_high_impact: boolean
}

export interface HydratedMutation {
  mutation_id: string
  protein: string
  identifiers: Record<string, unknown>
  estimated_effect: EffectType
  confidence: string
  justification: Record<string, unknown>
  [key: string]: unknown
  // Original raw CSV row — passed through from GuessMutation so detail views
  // and context cards can surface the original input fields.
  raw?: Record<string, unknown>
  // Drug-routing inputs sourced from the raw DepMap annotation (HugoSymbol /
  // ProteinChange / impact flags), which the LLM hydration can drop.
  hgvs_protein?: string   // protein-level variant (e.g. "p.L858R")
  gene?: string           // HugoSymbol gene symbol (e.g. "EGFR")
  features?: MutationFeatures
}

export interface SubgraphNode {
  id: string
  labels?: string[]
  label?: string
  symbol?: string
  [k: string]: unknown
}

export interface SubgraphEdge {
  source: string
  target: string
  type: string
  [k: string]: unknown
}

export interface Subgraph {
  nodes: SubgraphNode[]
  edges: SubgraphEdge[]
}

export interface DrugHit {
  drug_name: string
  drugbank_id: string
  approval_status: string
  mechanism: string
  gene_symbol: string  // the protein this drug targets
}

export type MutationStatus = 'identified' | 'hydrating' | 'done' | 'failed'

export interface MutationEntry {
  mutation_id: string
  status: MutationStatus
  hydrated?: HydratedMutation
  error?: string
}
