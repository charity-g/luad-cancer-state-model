import { useState, useEffect } from 'react'
import type { HydratedMutation, MutationEntry } from '../types'

interface GraphNode {
  id: string
  labels: string[]
  [key: string]: unknown
}

interface GraphEdge {
  type: string
  source: string
  target: string
  [key: string]: unknown
}

export interface ProfileGraph {
  nodes: GraphNode[]
  edges: GraphEdge[]
}

// Derive HydratedMutation highlights from the subgraph so PathwayGraph
// can colour nodes by effect without knowing about the graph shape.
export function extractHighlights(graph: ProfileGraph): HydratedMutation[] {
  const nodeById = Object.fromEntries(graph.nodes.map((n) => [n.id, n]))

  const highlights: HydratedMutation[] = []
  for (const edge of graph.edges) {
    if (edge.type !== 'AFFECTS') continue
    const mutation = nodeById[edge.source]
    const protein = nodeById[edge.target]
    if (!mutation || !protein) continue

    const geneSymbol =
      (protein.gene_symbol as string) ||
      (protein.kegg_gene_id as string) ||
      (protein.kegg_ko_id as string) ||
      (protein.id as string)

    highlights.push({
      mutation_id: (mutation.mutation_id as string) ?? (mutation.id as string),
      protein: geneSymbol,
      identifiers: (mutation.identifiers as Record<string, unknown>) ?? {},
      estimated_effect: (mutation.estimated_effect as string) as HydratedMutation['estimated_effect'],
      confidence: (mutation.confidence as string) ?? '',
      justification: (mutation.justification as Record<string, unknown>) ?? {},
    })
  }
  return highlights
}

function tryParseJson(v: unknown): Record<string, unknown> {
  if (v && typeof v === 'object') return v as Record<string, unknown>
  if (typeof v === 'string') {
    try { return JSON.parse(v) as Record<string, unknown> } catch { /* ignore */ }
  }
  return {}
}

// Build MutationEntry list from Mutation nodes in the subgraph.
export function extractMutations(graph: ProfileGraph): MutationEntry[] {
  return graph.nodes
    .filter((n) => n.labels?.includes('Mutation'))
    .map((n) => {
      const hydrated: HydratedMutation = {
        mutation_id:      String(n.mutation_id ?? n.id),
        protein:          String(n.protein ?? ''),
        identifiers:      tryParseJson(n.identifiers),
        estimated_effect: (n.estimated_effect as HydratedMutation['estimated_effect']) ?? 'uncertain',
        confidence:       String(n.confidence ?? ''),
        justification:    tryParseJson(n.justification),
      }
      return { mutation_id: hydrated.mutation_id, status: 'done' as const, hydrated }
    })
}

export function useProfileGraph(profileId: string | null) {
  const [graph, setGraph] = useState<ProfileGraph | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!profileId) {
      setGraph(null)
      return
    }

    let cancelled = false
    setLoading(true)
    setError(null)

    fetch(`/api/profiles/${profileId}/graph`)
      .then((r) => {
        if (!r.ok) throw new Error(`${r.status} ${r.statusText}`)
        return r.json() as Promise<ProfileGraph>
      })
      .then((data) => {
        if (!cancelled) {
          setGraph(data)
          setLoading(false)
        }
      })
      .catch((e: unknown) => {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : String(e))
          setLoading(false)
        }
      })

    return () => { cancelled = true }
  }, [profileId])

  return {
    graph,
    highlights: graph ? extractHighlights(graph) : [],
    mutations:  graph ? extractMutations(graph) : [],
    loading,
    error,
  }
}
