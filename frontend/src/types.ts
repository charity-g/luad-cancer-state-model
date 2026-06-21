export type EffectType = 'no_effect' | 'activating' | 'inactivating'

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
  estimated_effect: EffectType
  justification: Record<string, unknown>
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
