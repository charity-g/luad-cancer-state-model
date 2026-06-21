import type { HydratedMutation, EffectType } from '../types'

interface PathwayNode {
  id: string
  x: number
  y: number
  pathway: string
}

interface PathwayEdge {
  from: string
  to: string
  inhibitory?: boolean
}

const NODES: PathwayNode[] = [
  { id: 'EGFR',   x: 72,  y: 55,  pathway: 'RTK' },
  { id: 'ERBB2',  x: 72,  y: 120, pathway: 'RTK' },
  { id: 'ALK',    x: 72,  y: 185, pathway: 'RTK' },
  { id: 'MET',    x: 72,  y: 250, pathway: 'RTK' },
  { id: 'KEAP1',  x: 72,  y: 315, pathway: 'NRF2' },
  { id: 'KRAS',   x: 210, y: 130, pathway: 'MAPK' },
  { id: 'BRAF',   x: 330, y: 95,  pathway: 'MAPK' },
  { id: 'MEK',    x: 450, y: 95,  pathway: 'MAPK' },
  { id: 'ERK',    x: 565, y: 95,  pathway: 'MAPK' },
  { id: 'PIK3CA', x: 330, y: 230, pathway: 'PI3K' },
  { id: 'PTEN',   x: 210, y: 310, pathway: 'PI3K' },
  { id: 'AKT',    x: 450, y: 230, pathway: 'PI3K' },
  { id: 'mTOR',   x: 565, y: 230, pathway: 'PI3K' },
  { id: 'STK11',  x: 450, y: 330, pathway: 'AMPK' },
  { id: 'TP53',   x: 565, y: 330, pathway: 'TS' },
  { id: 'RB1',    x: 330, y: 330, pathway: 'TS' },
]

const EDGES: PathwayEdge[] = [
  { from: 'EGFR',   to: 'KRAS' },
  { from: 'EGFR',   to: 'PIK3CA' },
  { from: 'ERBB2',  to: 'KRAS' },
  { from: 'ALK',    to: 'KRAS' },
  { from: 'MET',    to: 'KRAS' },
  { from: 'KRAS',   to: 'BRAF' },
  { from: 'KRAS',   to: 'PIK3CA' },
  { from: 'BRAF',   to: 'MEK' },
  { from: 'MEK',    to: 'ERK' },
  { from: 'PIK3CA', to: 'AKT' },
  { from: 'AKT',    to: 'mTOR' },
  { from: 'PTEN',   to: 'PIK3CA', inhibitory: true },
  { from: 'STK11',  to: 'mTOR',   inhibitory: true },
  { from: 'TP53',   to: 'RB1' },
]

const PATHWAY_LABELS: Array<{ label: string; x: number; y: number }> = [
  { label: 'RTK', x: 72, y: 20 },
  { label: 'MAPK cascade', x: 450, y: 58 },
  { label: 'PI3K/AKT', x: 450, y: 195 },
  { label: 'Tumor suppressors', x: 450, y: 298 },
]

const NODE_R = 22

const effectNodeColor: Record<EffectType, string> = {
  activating: '#f59e0b',
  inactivating: '#ef4444',
  no_effect: '#06b6d4',
}

const effectGlow: Record<EffectType, string> = {
  activating: '#fbbf24',
  inactivating: '#f87171',
  no_effect: '#67e8f9',
}

interface Props {
  highlights: HydratedMutation[]
  selectedProtein?: string
}

export default function PathwayGraph({ highlights, selectedProtein }: Props) {
  const nodeById = Object.fromEntries(NODES.map((n) => [n.id, n]))
  const highlightMap = Object.fromEntries(highlights.map((h) => [h.protein, h]))

  return (
    <div className="flex h-full flex-col bg-slate-900">
      <div className="border-b border-slate-700 px-4 py-2.5">
        <p className="text-xs font-semibold uppercase tracking-widest text-slate-400">
          Protein Pathway Network
        </p>
        <div className="mt-1.5 flex gap-4">
          {[
            { label: 'Activating', color: '#f59e0b' },
            { label: 'Inactivating', color: '#ef4444' },
            { label: 'No effect', color: '#06b6d4' },
          ].map(({ label, color }) => (
            <div key={label} className="flex items-center gap-1.5">
              <span
                className="h-2.5 w-2.5 rounded-full"
                style={{ backgroundColor: color }}
              />
              <span className="text-[11px] text-slate-400">{label}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="flex flex-1 items-center justify-center overflow-hidden p-4">
        <svg
          viewBox="0 0 640 390"
          className="h-full w-full max-h-full"
          style={{ fontFamily: 'ui-monospace, monospace' }}
        >
          {/* Pathway region backgrounds */}
          <rect x="10" y="32" width="125" height="310" rx="8" fill="#1e293b" opacity="0.6" />
          <rect x="280" y="68" width="345" height="58" rx="6" fill="#1e293b" opacity="0.5" />
          <rect x="280" y="205" width="345" height="58" rx="6" fill="#1e293b" opacity="0.5" />
          <rect x="280" y="300" width="345" height="60" rx="6" fill="#1e293b" opacity="0.5" />

          {/* Pathway labels */}
          {PATHWAY_LABELS.map(({ label, x, y }) => (
            <text key={label} x={x} y={y} fontSize={9} fill="#475569" textAnchor="middle">
              {label}
            </text>
          ))}

          {/* Edges */}
          {EDGES.map((edge, i) => {
            const from = nodeById[edge.from]
            const to = nodeById[edge.to]
            if (!from || !to) return null
            const dx = to.x - from.x
            const dy = to.y - from.y
            const len = Math.sqrt(dx * dx + dy * dy)
            const ux = dx / len
            const uy = dy / len
            const x1 = from.x + ux * NODE_R
            const y1 = from.y + uy * NODE_R
            const x2 = to.x - ux * (NODE_R + 6)
            const y2 = to.y - uy * (NODE_R + 6)

            const isHighlighted =
              highlightMap[edge.from] || highlightMap[edge.to]

            return (
              <g key={i}>
                <line
                  x1={x1} y1={y1} x2={x2} y2={y2}
                  stroke={isHighlighted ? '#64748b' : '#334155'}
                  strokeWidth={isHighlighted ? 1.5 : 1}
                  strokeDasharray={edge.inhibitory ? '4 3' : undefined}
                />
                {/* arrowhead or flat bar */}
                {edge.inhibitory ? (
                  <line
                    x1={x2 - uy * 5} y1={y2 + ux * 5}
                    x2={x2 + uy * 5} y2={y2 - ux * 5}
                    stroke={isHighlighted ? '#64748b' : '#334155'}
                    strokeWidth={2}
                  />
                ) : (
                  <polygon
                    points={`${x2},${y2} ${x2 - ux * 7 - uy * 4},${y2 - uy * 7 + ux * 4} ${x2 - ux * 7 + uy * 4},${y2 - uy * 7 - ux * 4}`}
                    fill={isHighlighted ? '#64748b' : '#334155'}
                  />
                )}
              </g>
            )
          })}

          {/* Nodes */}
          {NODES.map((node) => {
            const h = highlightMap[node.id]
            const isSelected = node.id === selectedProtein
            const baseColor = h ? effectNodeColor[h.estimated_effect] : '#475569'
            const glowColor = h ? effectGlow[h.estimated_effect] : undefined

            return (
              <g key={node.id}>
                {/* glow ring */}
                {h && (
                  <circle
                    cx={node.x} cy={node.y} r={NODE_R + 7}
                    fill="none"
                    stroke={glowColor}
                    strokeWidth={isSelected ? 3 : 1.5}
                    opacity={isSelected ? 0.7 : 0.35}
                  />
                )}
                {isSelected && (
                  <circle
                    cx={node.x} cy={node.y} r={NODE_R + 13}
                    fill="none"
                    stroke={glowColor ?? '#94a3b8'}
                    strokeWidth={1}
                    opacity={0.2}
                  />
                )}
                {/* node circle */}
                <circle
                  cx={node.x} cy={node.y} r={NODE_R}
                  fill={h ? baseColor + '22' : '#1e293b'}
                  stroke={baseColor}
                  strokeWidth={h ? 2 : 1}
                />
                {/* label */}
                <text
                  x={node.x} y={node.y + 1}
                  textAnchor="middle"
                  dominantBaseline="middle"
                  fontSize={node.id.length > 5 ? 8 : 9}
                  fontWeight={h ? '700' : '500'}
                  fill={h ? baseColor : '#94a3b8'}
                >
                  {node.id}
                </text>
              </g>
            )
          })}
        </svg>
      </div>
    </div>
  )
}
