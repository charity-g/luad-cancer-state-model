export type EffectType = 'no_effect' | 'activating' | 'inactivating'

export interface ContextCard {
  id: string
  protein: string
  effect: EffectType
  mutation_id: string
  pathway?: string
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
  estimated_effect: EffectType
  justification: Record<string, unknown>
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

export type MutationStatus = 'identified' | 'hydrating' | 'done'

export interface MutationEntry {
  mutation_id: string
  status: MutationStatus
  hydrated?: HydratedMutation
}
