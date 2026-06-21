import { useEffect, useRef } from 'react'
import { Network } from 'vis-network/standalone'
import type { Subgraph, SubgraphNode } from '../types'

// The exact subgraph the agent traversed for an answer — its "reasoning path".
const COLORS: Record<string, string> = {
  Gene: '#3b82f6',
  Mutation: '#ef4444',
  Pathway: '#22c55e',
  Compound: '#a855f7',
  Disease: '#64748b',
}

function kind(n: SubgraphNode): string {
  return (n.labels && n.labels[0]) || '?'
}
function nodeLabel(n: SubgraphNode): string {
  return n.label || n.symbol || n.id
}

export default function SubgraphView({ subgraph }: { subgraph: Subgraph }) {
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!ref.current) return
    const nodes = subgraph.nodes.map((n) => ({
      id: n.id,
      label: nodeLabel(n),
      title: kind(n),
      color: COLORS[kind(n)] ?? '#94a3b8',
      shape: kind(n) === 'Pathway' ? 'box' : 'dot',
      size: 13,
    }))
    const edges = subgraph.edges.map((e) => ({
      from: e.source,
      to: e.target,
      label: e.type,
      arrows: 'to',
      font: { size: 8, color: '#64748b', strokeWidth: 2 },
      color: { color: '#cbd5e1', highlight: '#64748b' },
    }))
    const net = new Network(
      ref.current,
      { nodes, edges },
      {
        physics: { stabilization: true, barnesHut: { springLength: 110 } },
        nodes: { font: { size: 11 } },
        edges: { smooth: { enabled: true, type: 'dynamic' } },
        interaction: { hover: true },
      },
    )
    return () => net.destroy()
  }, [subgraph])

  return (
    <div className="mt-2">
      <div className="mb-1 flex items-center gap-2 text-[11px] text-slate-400">
        <span className="inline-flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-rose-500" />mutation</span>
        <span className="inline-flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-blue-500" />gene</span>
        <span className="inline-flex items-center gap-1"><span className="h-2 w-2 rounded-sm bg-green-500" />pathway</span>
        <span className="ml-auto">{subgraph.nodes.length} nodes · {subgraph.edges.length} edges</span>
      </div>
      <div ref={ref} className="h-64 w-full rounded-xl border border-slate-200 bg-slate-50" />
    </div>
  )
}
