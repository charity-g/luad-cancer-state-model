import type { Subgraph, SubgraphNode } from '../types'

// Renders the exact subgraph the agent traversed, in the dark SVG style of
// PathwayGraph. Auto-layout: columns by node type (mutation -> gene -> pathway),
// so the picture reads left-to-right as the path the agent took.

const KIND_COL: Record<string, number> = { Mutation: 0, Gene: 1, Pathway: 2, Compound: 3, Disease: 3 }
const KIND_COLOR: Record<string, string> = {
  Mutation: '#ef4444', Gene: '#3b82f6', Pathway: '#22c55e', Compound: '#a855f7', Disease: '#64748b',
}
const COL_X = [120, 360, 610, 800]
const COL_LABELS = ['Mutations', 'Genes', 'Pathways', 'Other']
const W = 920
const R = 20
const ROW = 72
const TOP = 52

function kind(n: SubgraphNode): string {
  return (n.labels && n.labels[0]) || 'Other'
}
function nodeLabel(n: SubgraphNode): string {
  return n.label || n.symbol || n.id
}
function colOf(n: SubgraphNode): number {
  return KIND_COL[kind(n)] ?? 3
}
function clip(s: string, n: number): string {
  return s.length > n ? s.slice(0, n - 1) + '…' : s
}

export default function SubgraphView({ subgraph }: { subgraph: Subgraph }) {
  const cols: SubgraphNode[][] = [[], [], [], []]
  for (const n of subgraph.nodes) cols[colOf(n)].push(n)
  const maxRows = Math.max(1, ...cols.map((c) => c.length))
  const H = TOP + maxRows * ROW

  const pos: Record<string, { x: number; y: number }> = {}
  cols.forEach((arr, ci) => {
    const colTop = TOP + ((maxRows - arr.length) * ROW) / 2
    arr.forEach((n, i) => {
      pos[n.id] = { x: COL_X[ci], y: colTop + i * ROW + ROW / 2 }
    })
  })

  const edges = subgraph.edges.filter(
    (e) => pos[e.source] && pos[e.target] && e.source !== e.target,
  )

  return (
    <div className="mt-2 overflow-hidden rounded-xl border border-slate-700 bg-slate-900">
      <div className="flex items-center justify-between border-b border-slate-700/60 px-3 py-1.5">
        <span className="text-[10px] font-semibold uppercase tracking-widest text-slate-400">
          Agent reasoning path
        </span>
        <div className="flex gap-3 text-[10px] text-slate-400">
          {(['Mutation', 'Gene', 'Pathway'] as const).map((k) => (
            <span key={k} className="flex items-center gap-1">
              <span className="h-2 w-2 rounded-full" style={{ background: KIND_COLOR[k] }} />
              {k.toLowerCase()}
            </span>
          ))}
          <span className="text-slate-500">{subgraph.nodes.length}n · {edges.length}e</span>
        </div>
      </div>

      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="w-full"
        style={{ maxHeight: 380, fontFamily: 'ui-monospace, monospace' }}
      >
        <defs>
          <marker id="sg-arrow" markerWidth="9" markerHeight="9" refX="7" refY="3" orient="auto">
            <path d="M0,0 L7,3 L0,6 Z" fill="#64748b" />
          </marker>
        </defs>

        {COL_LABELS.map((l, ci) =>
          cols[ci].length ? (
            <text key={l} x={COL_X[ci]} y={26} fontSize={10} fill="#475569" textAnchor="middle">{l}</text>
          ) : null,
        )}

        {edges.map((e, i) => {
          const s = pos[e.source], t = pos[e.target]
          const dx = t.x - s.x, dy = t.y - s.y
          const len = Math.hypot(dx, dy) || 1
          const ux = dx / len, uy = dy / len
          const x1 = s.x + ux * R, y1 = s.y + uy * R
          const x2 = t.x - ux * (R + 9), y2 = t.y - uy * (R + 9)
          return (
            <g key={i}>
              <line x1={x1} y1={y1} x2={x2} y2={y2} stroke="#475569" strokeWidth={1.2} markerEnd="url(#sg-arrow)" />
              <text x={(x1 + x2) / 2} y={(y1 + y2) / 2 - 3} fontSize={7.5} fill="#64748b" textAnchor="middle">
                {e.type}
              </text>
            </g>
          )
        })}

        {subgraph.nodes.map((n) => {
          const p = pos[n.id]
          if (!p) return null
          const k = kind(n)
          const color = KIND_COLOR[k] || '#94a3b8'
          const name = nodeLabel(n)
          if (k === 'Pathway') {
            const w = Math.min(160, Math.max(72, name.length * 6.2))
            return (
              <g key={n.id}>
                <rect x={p.x - w / 2} y={p.y - 14} width={w} height={28} rx={6} fill={color + '22'} stroke={color} strokeWidth={1.3} />
                <text x={p.x} y={p.y + 1} fontSize={8.5} fill={color} textAnchor="middle" dominantBaseline="middle">
                  {clip(name, 24)}
                </text>
              </g>
            )
          }
          return (
            <g key={n.id}>
              <circle cx={p.x} cy={p.y} r={R} fill={color + '22'} stroke={color} strokeWidth={1.6} />
              <text x={p.x} y={p.y + R + 11} fontSize={8.5} fill="#cbd5e1" textAnchor="middle">{clip(name, 18)}</text>
            </g>
          )
        })}
      </svg>
    </div>
  )
}
