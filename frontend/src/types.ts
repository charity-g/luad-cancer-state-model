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
}

export interface HydratedMutation {
  mutation_id: string
  protein: string
  identifiers: Record<string, unknown>
  estimated_effect: EffectType
  confidence: string
  justification: Record<string, unknown>
  [key: string]: unknown
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

export type MutationStatus = 'identified' | 'hydrating' | 'done' | 'failed'

export interface MutationEntry {
  mutation_id: string
  status: MutationStatus
  hydrated?: HydratedMutation
  error?: string
}
