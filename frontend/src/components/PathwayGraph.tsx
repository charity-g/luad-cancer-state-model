import { useState, useRef } from 'react'
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

const VIEWBOX_W = 640
const VIEWBOX_H = 390
const NODE_R = 22

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

const PATHWAY_LABELS = [
  { label: 'RTK receptors', x: 72,  y: 20 },
  { label: 'MAPK cascade',  x: 450, y: 58 },
  { label: 'PI3K / AKT',   x: 450, y: 195 },
  { label: 'Tumor suppressors', x: 450, y: 298 },
]

interface ProteinMeta {
  fullName: string
  pathway: string
  role: string
  mechanism: string
  frequency: string
  drugs?: string[]
}

const PROTEIN_META: Record<string, ProteinMeta> = {
  EGFR:   { fullName: 'Epidermal Growth Factor Receptor', pathway: 'RTK/MAPK', role: 'Receptor tyrosine kinase', mechanism: 'Ligand-activated kinase driving RAS/MAPK and PI3K/AKT', frequency: '~15% LUAD', drugs: ['Erlotinib', 'Gefitinib', 'Osimertinib'] },
  ERBB2:  { fullName: 'Receptor Tyrosine-Protein Kinase ErbB-2', pathway: 'RTK/MAPK', role: 'Receptor tyrosine kinase', mechanism: 'Exon 20 insertions or amplification activate downstream signaling', frequency: '~3% LUAD', drugs: ['Trastuzumab', 'Afatinib'] },
  ALK:    { fullName: 'Anaplastic Lymphoma Kinase', pathway: 'RTK/MAPK', role: 'Receptor tyrosine kinase', mechanism: 'Fusion proteins (EML4-ALK) drive constitutive kinase activation', frequency: '~5% LUAD', drugs: ['Crizotinib', 'Alectinib', 'Lorlatinib'] },
  MET:    { fullName: 'MET Proto-Oncogene', pathway: 'RTK/MAPK', role: 'Receptor tyrosine kinase', mechanism: 'Exon 14 skipping or amplification → uncontrolled signaling', frequency: '~3–5% LUAD', drugs: ['Capmatinib', 'Tepotinib'] },
  KEAP1:  { fullName: 'Kelch-like ECH-Associated Protein 1', pathway: 'NRF2/Oxidative Stress', role: 'E3 ubiquitin ligase adaptor', mechanism: 'LOF releases NRF2, promoting antioxidant gene expression and chemo-resistance', frequency: '~20% LUAD' },
  KRAS:   { fullName: 'Kirsten Rat Sarcoma Viral Proto-oncogene', pathway: 'RAS/MAPK', role: 'GTPase signal transducer', mechanism: 'Constitutively GTP-bound state drives unchecked proliferation', frequency: '~30% LUAD', drugs: ['Sotorasib (G12C)', 'Adagrasib (G12C)'] },
  BRAF:   { fullName: 'B-Raf Proto-Oncogene', pathway: 'MAPK', role: 'Serine/threonine kinase', mechanism: 'V600E and other activating mutations hyperactivate MEK–ERK', frequency: '~5–7% LUAD', drugs: ['Dabrafenib', 'Trametinib'] },
  MEK:    { fullName: 'Mitogen-Activated Protein Kinase Kinase', pathway: 'MAPK', role: 'Dual-specificity kinase', mechanism: 'Phosphorylates and activates ERK1/2 downstream of RAS/RAF', frequency: 'Rare direct mutation' },
  ERK:    { fullName: 'Extracellular Signal-Regulated Kinase', pathway: 'MAPK', role: 'Serine/threonine kinase', mechanism: 'Terminal MAPK effector; drives transcription of proliferative genes', frequency: 'Rare direct mutation' },
  PIK3CA: { fullName: 'Phosphatidylinositol-4,5-Bisphosphate 3-Kinase Catalytic Subunit Alpha', pathway: 'PI3K/AKT/mTOR', role: 'Lipid kinase', mechanism: 'GOF mutations increase PIP3 production, activating AKT', frequency: '~7% LUAD', drugs: ['Alpelisib'] },
  PTEN:   { fullName: 'Phosphatase and Tensin Homolog', pathway: 'PI3K/AKT/mTOR', role: 'Lipid phosphatase tumor suppressor', mechanism: 'Dephosphorylates PIP3; loss unleashes PI3K/AKT signaling', frequency: '~5% LUAD' },
  AKT:    { fullName: 'AKT Serine/Threonine Kinase', pathway: 'PI3K/AKT/mTOR', role: 'Serine/threonine kinase', mechanism: 'Central node promoting survival, growth, and mTOR activation', frequency: 'Rare direct mutation' },
  mTOR:   { fullName: 'Mechanistic Target of Rapamycin', pathway: 'PI3K/AKT/mTOR', role: 'Serine/threonine kinase complex', mechanism: 'Integrates nutrient and growth signals to control protein synthesis', frequency: 'Rare direct mutation', drugs: ['Everolimus', 'Temsirolimus'] },
  STK11:  { fullName: 'Serine/Threonine Kinase 11 (LKB1)', pathway: 'AMPK/mTOR', role: 'Master kinase tumor suppressor', mechanism: 'LOF impairs AMPK activation, removing mTOR brake; linked to immunotherapy resistance', frequency: '~20% LUAD' },
  TP53:   { fullName: 'Tumor Protein P53', pathway: 'Cell Cycle / Apoptosis', role: 'Transcription factor tumor suppressor', mechanism: 'LOF abrogates G1/S checkpoint, DNA repair signaling, and apoptosis', frequency: '~50% LUAD' },
  RB1:    { fullName: 'Retinoblastoma Protein 1', pathway: 'Cell Cycle', role: 'Tumor suppressor / E2F repressor', mechanism: 'LOF releases E2F transcription factors, driving S-phase entry', frequency: '~4% LUAD' },
}

const effectNodeColor: Record<EffectType, string> = {
  activating:   '#f59e0b',
  inactivating: '#ef4444',
  no_effect:    '#06b6d4',
}
const effectGlow: Record<EffectType, string> = {
  activating:   '#fbbf24',
  inactivating: '#f87171',
  no_effect:    '#67e8f9',
}
const effectLabel: Record<EffectType, string> = {
  activating:   'Activating',
  inactivating: 'Inactivating',
  no_effect:    'No Effect',
}
const effectBadge: Record<EffectType, string> = {
  activating:   'bg-amber-100 text-amber-800',
  inactivating: 'bg-red-100 text-red-800',
  no_effect:    'bg-cyan-100 text-cyan-800',
}

interface Props {
  highlights: HydratedMutation[]
  selectedProtein?: string
}

export default function PathwayGraph({ highlights, selectedProtein }: Props) {
  const [hoveredNode, setHoveredNode] = useState<string | null>(null)
  const [clickedNode, setClickedNode] = useState<string | null>(null)
  const svgRef = useRef<SVGSVGElement>(null)

  const nodeById = Object.fromEntries(NODES.map((n) => [n.id, n]))
  const highlightMap = Object.fromEntries(highlights.map((h) => [h.protein, h]))

  function handleNodeClick(id: string) {
    setClickedNode((prev) => (prev === id ? null : id))
  }

  // Convert SVG viewBox coords → CSS % for popover positioning
  function svgToPercent(x: number, y: number) {
    return {
      left: `${(x / VIEWBOX_W) * 100}%`,
      top:  `${(y / VIEWBOX_H) * 100}%`,
    }
  }

  const popoverNode = clickedNode ? nodeById[clickedNode] : null
  const popoverMeta = clickedNode ? PROTEIN_META[clickedNode] : null
  const popoverEffect = clickedNode ? highlightMap[clickedNode] : null

  // Flip popover to left if node is in right half
  const flipLeft = popoverNode ? popoverNode.x > VIEWBOX_W / 2 : false
  const flipUp   = popoverNode ? popoverNode.y > VIEWBOX_H * 0.6 : false

  return (
    <div className="relative flex h-full w-full flex-col bg-slate-900">
      {/* Legend */}
      <div className="flex flex-shrink-0 items-center justify-between border-b border-slate-700/60 px-4 py-2">
        <p className="text-xs font-semibold uppercase tracking-widest text-slate-400">
          Protein Pathway Network
        </p>
        <div className="flex gap-4">
          {([['activating', '#f59e0b'], ['inactivating', '#ef4444'], ['no effect', '#06b6d4']] as const).map(
            ([label, color]) => (
              <div key={label} className="flex items-center gap-1.5">
                <span className="h-2 w-2 rounded-full" style={{ backgroundColor: color }} />
                <span className="text-[11px] capitalize text-slate-400">{label}</span>
              </div>
            ),
          )}
        </div>
      </div>

      {/* SVG graph */}
      <div className="relative flex-1 overflow-hidden">
        <svg
          ref={svgRef}
          viewBox={`0 0 ${VIEWBOX_W} ${VIEWBOX_H}`}
          className="h-full w-full cursor-default"
          style={{ fontFamily: 'ui-monospace, monospace' }}
          onClick={(e) => {
            if ((e.target as SVGElement).tagName === 'svg') setClickedNode(null)
          }}
        >
          {/* Region backgrounds */}
          <rect x="10"  y="32"  width="125" height="310" rx="8" fill="#1e293b" opacity="0.5" />
          <rect x="280" y="68"  width="345" height="55"  rx="6" fill="#1e293b" opacity="0.4" />
          <rect x="280" y="205" width="345" height="55"  rx="6" fill="#1e293b" opacity="0.4" />
          <rect x="280" y="300" width="345" height="58"  rx="6" fill="#1e293b" opacity="0.4" />

          {PATHWAY_LABELS.map(({ label, x, y }) => (
            <text key={label} x={x} y={y} fontSize={9} fill="#475569" textAnchor="middle">{label}</text>
          ))}

          {/* Edges */}
          {EDGES.map((edge, i) => {
            const from = nodeById[edge.from]
            const to   = nodeById[edge.to]
            if (!from || !to) return null
            const dx = to.x - from.x, dy = to.y - from.y
            const len = Math.sqrt(dx * dx + dy * dy)
            const ux = dx / len, uy = dy / len
            const x1 = from.x + ux * NODE_R, y1 = from.y + uy * NODE_R
            const x2 = to.x - ux * (NODE_R + 6), y2 = to.y - uy * (NODE_R + 6)
            const lit = highlightMap[edge.from] || highlightMap[edge.to]
              || hoveredNode === edge.from || hoveredNode === edge.to
            return (
              <g key={i}>
                <line x1={x1} y1={y1} x2={x2} y2={y2}
                  stroke={lit ? '#64748b' : '#1e293b'} strokeWidth={lit ? 1.5 : 1}
                  strokeDasharray={edge.inhibitory ? '4 3' : undefined}
                />
                {edge.inhibitory ? (
                  <line x1={x2 - uy * 5} y1={y2 + ux * 5} x2={x2 + uy * 5} y2={y2 - ux * 5}
                    stroke={lit ? '#64748b' : '#1e293b'} strokeWidth={2} />
                ) : (
                  <polygon
                    points={`${x2},${y2} ${x2 - ux * 7 - uy * 4},${y2 - uy * 7 + ux * 4} ${x2 - ux * 7 + uy * 4},${y2 - uy * 7 - ux * 4}`}
                    fill={lit ? '#64748b' : '#1e293b'} />
                )}
              </g>
            )
          })}

          {/* Nodes */}
          {NODES.map((node) => {
            const h       = highlightMap[node.id]
            const isHover = hoveredNode === node.id
            const isClick = clickedNode === node.id
            const isSel   = node.id === selectedProtein
            const baseColor = h ? effectNodeColor[h.estimated_effect] : (isHover ? '#94a3b8' : '#334155')
            const glowColor = h ? effectGlow[h.estimated_effect] : '#94a3b8'
            const r = isHover || isClick ? NODE_R + 3 : NODE_R

            return (
              <g
                key={node.id}
                style={{ cursor: 'pointer' }}
                onClick={(e) => { e.stopPropagation(); handleNodeClick(node.id) }}
                onMouseEnter={() => setHoveredNode(node.id)}
                onMouseLeave={() => setHoveredNode(null)}
              >
                {/* outer glow rings */}
                {(h || isHover || isClick || isSel) && (
                  <circle cx={node.x} cy={node.y} r={r + 8}
                    fill="none" stroke={glowColor} strokeWidth={isClick ? 2.5 : 1.5}
                    opacity={isClick ? 0.6 : 0.25} />
                )}
                {(isClick || isSel) && (
                  <circle cx={node.x} cy={node.y} r={r + 16}
                    fill="none" stroke={glowColor} strokeWidth={1} opacity={0.12} />
                )}
                {/* node fill */}
                <circle cx={node.x} cy={node.y} r={r}
                  fill={h || isHover ? baseColor + '20' : '#0f172a'}
                  stroke={baseColor} strokeWidth={isClick ? 2.5 : h ? 2 : 1}
                />
                <text x={node.x} y={node.y + 1}
                  textAnchor="middle" dominantBaseline="middle"
                  fontSize={node.id.length > 5 ? 8 : 9}
                  fontWeight={h || isHover ? '700' : '500'}
                  fill={h ? baseColor : isHover ? '#cbd5e1' : '#64748b'}
                  style={{ pointerEvents: 'none', userSelect: 'none' }}
                >
                  {node.id}
                </text>
              </g>
            )
          })}
        </svg>

        {/* Popover card */}
        {popoverNode && popoverMeta && (
          <div
            className="pointer-events-auto absolute z-20 w-64 rounded-xl border border-slate-700 bg-slate-800 shadow-2xl"
            style={{
              ...svgToPercent(popoverNode.x, popoverNode.y),
              transform: `translate(${flipLeft ? 'calc(-100% - 12px)' : '12px'}, ${flipUp ? 'calc(-100% + 12px)' : '-50%'})`,
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-start justify-between px-4 pt-3 pb-2">
              <div>
                <p className="font-mono text-base font-bold text-slate-100">{clickedNode}</p>
                <p className="text-[11px] text-slate-400 leading-tight">{popoverMeta.fullName}</p>
              </div>
              <button
                onClick={() => setClickedNode(null)}
                className="ml-2 mt-0.5 flex-shrink-0 rounded p-1 text-slate-500 hover:bg-slate-700 hover:text-slate-300"
              >
                <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            {popoverEffect && (
              <div className="mx-3 mb-2 rounded-lg px-3 py-1.5"
                style={{ backgroundColor: effectNodeColor[popoverEffect.estimated_effect] + '18',
                         border: `1px solid ${effectNodeColor[popoverEffect.estimated_effect]}44` }}>
                <div className="flex items-center gap-2">
                  <span className="h-1.5 w-1.5 rounded-full flex-shrink-0"
                    style={{ backgroundColor: effectNodeColor[popoverEffect.estimated_effect] }} />
                  <span className="text-xs font-semibold"
                    style={{ color: effectNodeColor[popoverEffect.estimated_effect] }}>
                    {effectLabel[popoverEffect.estimated_effect]}
                  </span>
                  <span className="ml-auto text-[10px] text-slate-400">{popoverEffect.mutation_id}</span>
                </div>
              </div>
            )}

            <div className="divide-y divide-slate-700/50 px-4 pb-3">
              <div className="py-2">
                <p className="text-[10px] font-medium uppercase tracking-wider text-slate-500">Pathway</p>
                <p className="mt-0.5 text-xs text-slate-300">{popoverMeta.pathway}</p>
              </div>
              <div className="py-2">
                <p className="text-[10px] font-medium uppercase tracking-wider text-slate-500">Role</p>
                <p className="mt-0.5 text-xs text-slate-300">{popoverMeta.role}</p>
              </div>
              <div className="py-2">
                <p className="text-[10px] font-medium uppercase tracking-wider text-slate-500">Mechanism</p>
                <p className="mt-0.5 text-xs leading-relaxed text-slate-400">{popoverMeta.mechanism}</p>
              </div>
              <div className="py-2">
                <p className="text-[10px] font-medium uppercase tracking-wider text-slate-500">Frequency in LUAD</p>
                <p className="mt-0.5 text-xs text-slate-300">{popoverMeta.frequency}</p>
              </div>
              {popoverMeta.drugs && (
                <div className="pt-2">
                  <p className="mb-1.5 text-[10px] font-medium uppercase tracking-wider text-slate-500">Targeted Agents</p>
                  <div className="flex flex-wrap gap-1">
                    {popoverMeta.drugs.map((d) => (
                      <span key={d} className="rounded bg-slate-700 px-1.5 py-0.5 text-[10px] text-slate-300">{d}</span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
