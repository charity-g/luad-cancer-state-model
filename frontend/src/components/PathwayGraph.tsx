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

const VIEWBOX_W = 780
const VIEWBOX_H = 390
const NODE_R = 22

// Terminal outcome nodes (rendered as rounded rects, not circles)
const OUTCOME_W = 78
const OUTCOME_H = 30
const OUTCOMES = [
  { id: 'Proliferation', x: 700, y: 140, label: 'Cell Proliferation', color: '#a78bfa' },
  { id: 'Apoptosis',     x: 700, y: 310, label: 'Apoptosis',          color: '#34d399' },
]

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
  // Outcome edges
  { from: 'ERK',   to: 'Proliferation' },
  { from: 'mTOR',  to: 'Proliferation' },
  { from: 'RB1',   to: 'Proliferation', inhibitory: true },
  { from: 'TP53',  to: 'Apoptosis' },
]

const PATHWAY_LABELS = [
  { label: 'RTK receptors',    x: 72,  y: 20 },
  { label: 'MAPK cascade',     x: 450, y: 58 },
  { label: 'PI3K / AKT',      x: 450, y: 195 },
  { label: 'Tumor suppressors', x: 450, y: 298 },
  { label: 'Outcomes',         x: 700, y: 20 },
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
  TP53:          { fullName: 'Tumor Protein P53', pathway: 'Cell Cycle / Apoptosis', role: 'Transcription factor tumor suppressor', mechanism: 'LOF abrogates G1/S checkpoint, DNA repair signaling, and apoptosis', frequency: '~50% LUAD' },
  RB1:           { fullName: 'Retinoblastoma Protein 1', pathway: 'Cell Cycle', role: 'Tumor suppressor / E2F repressor', mechanism: 'LOF releases E2F transcription factors, driving S-phase entry', frequency: '~4% LUAD' },
  Proliferation: { fullName: 'Cell Proliferation', pathway: 'Outcome', role: 'Cellular outcome', mechanism: 'Driven by ERK and mTOR activation; counteracted by RB1-mediated G1/S arrest. Hyperactivation leads to unchecked tumor growth.', frequency: 'Hallmark of cancer' },
  Apoptosis:     { fullName: 'Apoptosis (Programmed Cell Death)', pathway: 'Outcome', role: 'Cellular outcome', mechanism: 'Promoted by TP53-driven transcription of pro-apoptotic genes (BAX, PUMA). TP53 loss is the primary escape mechanism in LUAD.', frequency: 'Hallmark of cancer' },
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
  onDiveDeeper?: (context: string) => void
}

export default function PathwayGraph({ highlights, selectedProtein, onDiveDeeper }: Props) {
  const [hoveredNode, setHoveredNode] = useState<string | null>(null)
  const [clickedNode, setClickedNode] = useState<string | null>(null)
  const svgRef = useRef<SVGSVGElement>(null)

  const nodeById    = Object.fromEntries(NODES.map((n) => [n.id, n]))
  const outcomeById = Object.fromEntries(OUTCOMES.map((o) => [o.id, o]))
  const highlightMap = Object.fromEntries(highlights.map((h) => [h.protein, h]))

  function handleNodeClick(id: string) {
    setClickedNode((prev) => (prev === id ? null : id))
  }

  function svgToPercent(x: number, y: number) {
    return {
      left: `${(x / VIEWBOX_W) * 100}%`,
      top:  `${(y / VIEWBOX_H) * 100}%`,
    }
  }

  // Resolve click target — may be a protein node or an outcome node
  const popoverProteinNode = clickedNode ? nodeById[clickedNode] : null
  const popoverOutcomeNode = clickedNode ? outcomeById[clickedNode] : null
  const popoverAnchorX = popoverProteinNode?.x ?? popoverOutcomeNode?.x ?? 0
  const popoverAnchorY = popoverProteinNode?.y ?? popoverOutcomeNode?.y ?? 0
  const popoverMeta    = clickedNode ? PROTEIN_META[clickedNode] : null
  const popoverEffect  = clickedNode ? highlightMap[clickedNode] : null

  const flipLeft = popoverAnchorX > VIEWBOX_W / 2
  const flipUp   = popoverAnchorY > VIEWBOX_H * 0.6

  function buildDiveDeeperContext(protein: string, meta: ProteinMeta, effect?: HydratedMutation) {
    const lines = [
      `Dive deeper on ${protein} in this LUAD pathway model.`,
      `Protein context: ${meta.fullName}; pathway: ${meta.pathway}; role: ${meta.role}; mechanism: ${meta.mechanism}; LUAD frequency: ${meta.frequency}.`,
    ]

    if (meta.drugs?.length) {
      lines.push(`Targeted agents shown: ${meta.drugs.join(', ')}.`)
    }

    if (effect) {
      lines.push(`Current sample mutation: ${effect.mutation_id}; estimated effect: ${effectLabel[effect.estimated_effect]}.`)
      const justification = Object.entries(effect.justification)
        .map(([key, val]) => `${key.replace(/_/g, ' ')}: ${String(val)}`)
        .join('; ')

      if (justification) {
        lines.push(`Annotation justification: ${justification}.`)
      }
    }

    lines.push('Explain the likely pathway-level impact and what follow-up evidence would be most useful.')
    return lines.join(' ')
  }

  // Edge endpoint helpers
  function edgeStart(id: string, tx: number, ty: number) {
    const n = nodeById[id]
    if (!n) return { x: 0, y: 0 }
    const dx = tx - n.x, dy = ty - n.y
    const len = Math.sqrt(dx * dx + dy * dy) || 1
    return { x: n.x + (dx / len) * NODE_R, y: n.y + (dy / len) * NODE_R }
  }

  function edgeEnd(id: string, fx: number, fy: number) {
    const o = outcomeById[id]
    if (o) {
      // Hit the left edge of the outcome rect
      return { x: o.x - OUTCOME_W / 2, y: o.y, isOutcome: true }
    }
    const n = nodeById[id]
    if (!n) return { x: 0, y: 0, isOutcome: false }
    const dx = n.x - fx, dy = n.y - fy
    const len = Math.sqrt(dx * dx + dy * dy) || 1
    return { x: n.x - (dx / len) * (NODE_R + 6), y: n.y - (dy / len) * (NODE_R + 6), isOutcome: false }
  }

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
          {/* Outcomes column background */}
          <rect x="655" y="32"  width="110" height="340" rx="8" fill="#1e293b" opacity="0.35" />

          {PATHWAY_LABELS.map(({ label, x, y }) => (
            <text key={label} x={x} y={y} fontSize={9} fill="#475569" textAnchor="middle">{label}</text>
          ))}

          {/* Edges */}
          {EDGES.map((edge, i) => {
            const toOutcome = !!outcomeById[edge.to]
            const toNode    = nodeById[edge.to]
            const tx = toOutcome ? outcomeById[edge.to].x : toNode?.x ?? 0
            const ty = toOutcome ? outcomeById[edge.to].y : toNode?.y ?? 0

            const s = edgeStart(edge.from, tx, ty)
            const e2 = edgeEnd(edge.to, s.x, s.y)
            if (!s || !e2) return null

            const dx = e2.x - s.x, dy = e2.y - s.y
            const len = Math.sqrt(dx * dx + dy * dy) || 1
            const ux = dx / len, uy = dy / len

            const lit = highlightMap[edge.from] || highlightMap[edge.to]
              || hoveredNode === edge.from || hoveredNode === edge.to
              || clickedNode === edge.from || clickedNode === edge.to

            const stroke    = lit ? '#64748b' : '#1e293b'
            const arrowEnd  = { x: e2.x - ux * 6, y: e2.y - uy * 6 }

            return (
              <g key={i}>
                <line x1={s.x} y1={s.y} x2={arrowEnd.x} y2={arrowEnd.y}
                  stroke={stroke} strokeWidth={lit ? 1.5 : 1}
                  strokeDasharray={edge.inhibitory ? '4 3' : undefined}
                />
                {edge.inhibitory ? (
                  <line x1={arrowEnd.x - uy * 5} y1={arrowEnd.y + ux * 5}
                        x2={arrowEnd.x + uy * 5} y2={arrowEnd.y - ux * 5}
                    stroke={stroke} strokeWidth={2} />
                ) : (
                  <polygon
                    points={`${e2.x},${e2.y} ${e2.x - ux * 7 - uy * 4},${e2.y - uy * 7 + ux * 4} ${e2.x - ux * 7 + uy * 4},${e2.y - uy * 7 - ux * 4}`}
                    fill={stroke} />
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

          {/* Outcome nodes (rounded rects) */}
          {OUTCOMES.map((outcome) => {
            const isHover = hoveredNode === outcome.id
            const isClick = clickedNode === outcome.id
            const w = isHover || isClick ? OUTCOME_W + 6 : OUTCOME_W
            const h = isHover || isClick ? OUTCOME_H + 4 : OUTCOME_H
            return (
              <g
                key={outcome.id}
                style={{ cursor: 'pointer' }}
                onClick={(e) => { e.stopPropagation(); handleNodeClick(outcome.id) }}
                onMouseEnter={() => setHoveredNode(outcome.id)}
                onMouseLeave={() => setHoveredNode(null)}
              >
                {/* glow */}
                {(isHover || isClick) && (
                  <rect x={outcome.x - w / 2 - 6} y={outcome.y - h / 2 - 6}
                    width={w + 12} height={h + 12} rx="10"
                    fill="none" stroke={outcome.color} strokeWidth={1.5}
                    opacity={isClick ? 0.5 : 0.2} />
                )}
                <rect
                  x={outcome.x - w / 2} y={outcome.y - h / 2}
                  width={w} height={h} rx="6"
                  fill={isHover || isClick ? outcome.color + '22' : outcome.color + '12'}
                  stroke={outcome.color}
                  strokeWidth={isClick ? 2 : 1.5}
                />
                <text x={outcome.x} y={outcome.y + 1}
                  textAnchor="middle" dominantBaseline="middle"
                  fontSize={8} fontWeight={isHover || isClick ? '700' : '600'}
                  fill={outcome.color}
                  style={{ pointerEvents: 'none', userSelect: 'none' }}
                >
                  {outcome.label}
                </text>
              </g>
            )
          })}
        </svg>

        {/* Popover card */}
        {(popoverProteinNode || popoverOutcomeNode) && popoverMeta && (
          <div
            className="pointer-events-auto absolute z-20 w-64 rounded-xl border border-slate-700 bg-slate-800 shadow-2xl"
            style={{
              ...svgToPercent(popoverAnchorX, popoverAnchorY),
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
              {popoverProteinNode && onDiveDeeper && clickedNode && (
                <div className="pt-3">
                  <button
                    onClick={() => onDiveDeeper(buildDiveDeeperContext(clickedNode, popoverMeta, popoverEffect))}
                    className="flex w-full items-center justify-center gap-2 rounded-lg border border-slate-600 bg-slate-700 px-3 py-2 text-xs font-semibold text-slate-100 transition-colors hover:border-slate-500 hover:bg-slate-600"
                  >
                    <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                        d="M13 7h6m0 0v6m0-6l-8 8-4-4-5 5" />
                    </svg>
                    Dive deeper with agent
                  </button>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
