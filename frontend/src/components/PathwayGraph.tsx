import { useState, useRef } from 'react'
import type { HydratedMutation, EffectType, ContextCard } from '../types'
import { useProfileGraph, type ProfileGraph } from '../hooks/useProfileGraph'

// ---------------------------------------------------------------------------
// Static fallback graph (hardcoded LUAD diagram shown when no profile loaded)
// ---------------------------------------------------------------------------

interface StaticNode { id: string; x: number; y: number; pathway: string }
interface StaticEdge { from: string; to: string; inhibitory?: boolean }

const VIEWBOX_W = 780
const VIEWBOX_H = 390
const NODE_R = 22
const OUTCOME_W = 78
const OUTCOME_H = 30

const OUTCOMES = [
  { id: 'Proliferation', x: 700, y: 140, label: 'Cell Proliferation', color: '#a78bfa' },
  { id: 'Apoptosis',     x: 700, y: 310, label: 'Apoptosis',          color: '#34d399' },
]

const STATIC_NODES: StaticNode[] = [
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

const STATIC_EDGES: StaticEdge[] = [
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
  { from: 'ERK',    to: 'Proliferation' },
  { from: 'mTOR',   to: 'Proliferation' },
  { from: 'RB1',    to: 'Proliferation', inhibitory: true },
  { from: 'TP53',   to: 'Apoptosis' },
]

const PATHWAY_LABELS = [
  { label: 'RTK receptors',     x: 72,  y: 20 },
  { label: 'MAPK cascade',      x: 450, y: 58 },
  { label: 'PI3K / AKT',       x: 450, y: 195 },
  { label: 'Tumor suppressors', x: 450, y: 298 },
  { label: 'Outcomes',          x: 700, y: 20 },
]

interface ProteinMeta {
  fullName: string; pathway: string; role: string; mechanism: string; frequency: string; drugs?: string[]
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
  PIK3CA: { fullName: 'PI-4,5-Bisphosphate 3-Kinase Catalytic Subunit Alpha', pathway: 'PI3K/AKT/mTOR', role: 'Lipid kinase', mechanism: 'GOF mutations increase PIP3 production, activating AKT', frequency: '~7% LUAD', drugs: ['Alpelisib'] },
  PTEN:   { fullName: 'Phosphatase and Tensin Homolog', pathway: 'PI3K/AKT/mTOR', role: 'Lipid phosphatase tumor suppressor', mechanism: 'Dephosphorylates PIP3; loss unleashes PI3K/AKT signaling', frequency: '~5% LUAD' },
  AKT:    { fullName: 'AKT Serine/Threonine Kinase', pathway: 'PI3K/AKT/mTOR', role: 'Serine/threonine kinase', mechanism: 'Central node promoting survival, growth, and mTOR activation', frequency: 'Rare direct mutation' },
  mTOR:   { fullName: 'Mechanistic Target of Rapamycin', pathway: 'PI3K/AKT/mTOR', role: 'Serine/threonine kinase complex', mechanism: 'Integrates nutrient and growth signals to control protein synthesis', frequency: 'Rare direct mutation', drugs: ['Everolimus', 'Temsirolimus'] },
  STK11:  { fullName: 'Serine/Threonine Kinase 11 (LKB1)', pathway: 'AMPK/mTOR', role: 'Master kinase tumor suppressor', mechanism: 'LOF impairs AMPK activation, removing mTOR brake; linked to immunotherapy resistance', frequency: '~20% LUAD' },
  TP53:   { fullName: 'Tumor Protein P53', pathway: 'Cell Cycle / Apoptosis', role: 'Transcription factor tumor suppressor', mechanism: 'LOF abrogates G1/S checkpoint, DNA repair signaling, and apoptosis', frequency: '~50% LUAD' },
  RB1:    { fullName: 'Retinoblastoma Protein 1', pathway: 'Cell Cycle', role: 'Tumor suppressor / E2F repressor', mechanism: 'LOF releases E2F transcription factors, driving S-phase entry', frequency: '~4% LUAD' },
  Proliferation: { fullName: 'Cell Proliferation', pathway: 'Outcome', role: 'Cellular outcome', mechanism: 'Driven by ERK and mTOR activation; counteracted by RB1-mediated G1/S arrest.', frequency: 'Hallmark of cancer' },
  Apoptosis:     { fullName: 'Apoptosis (Programmed Cell Death)', pathway: 'Outcome', role: 'Cellular outcome', mechanism: 'Promoted by TP53-driven transcription of pro-apoptotic genes (BAX, PUMA).', frequency: 'Hallmark of cancer' },
}

// ---------------------------------------------------------------------------
// Shared effect colour maps
// ---------------------------------------------------------------------------

const effectNodeColor: Record<EffectType, string> = {
  activating:       '#f59e0b',
  gain_of_function: '#f59e0b',
  inactivating:     '#ef4444',
  loss_of_function: '#ef4444',
  uncertain:        '#a78bfa',
  no_effect:        '#06b6d4',
}
const effectGlow: Record<EffectType, string> = {
  activating:       '#fbbf24',
  gain_of_function: '#fbbf24',
  inactivating:     '#f87171',
  loss_of_function: '#f87171',
  uncertain:        '#c4b5fd',
  no_effect:        '#67e8f9',
}
const effectLabel: Record<EffectType, string> = {
  activating:       'Activating',
  gain_of_function: 'Gain of Function',
  inactivating:     'Inactivating',
  loss_of_function: 'Loss of Function',
  uncertain:        'Uncertain',
  no_effect:        'No Effect',
}

// ---------------------------------------------------------------------------
// Dynamic layout — tiered left-to-right from backend graph data
// ---------------------------------------------------------------------------

interface LayoutNode {
  id: string
  x: number
  y: number
  label: string        // display text inside the circle
  nodeLabel: string    // Neo4j label: Mutation | Protein | Pathway
  props: Record<string, unknown>
}

interface LayoutEdge {
  source: string
  target: string
  type: string
}

function computeLayout(graph: ProfileGraph): { nodes: LayoutNode[]; edges: LayoutEdge[] } {
  const PAD_TOP = 40
  const PAD_BOT = 350

  const mutations = graph.nodes.filter((n) => n.labels.includes('Mutation'))
  const proteins  = graph.nodes.filter((n) => n.labels.includes('Protein'))
  const pathways  = graph.nodes.filter((n) => n.labels.includes('Pathway'))

  function tier(nodes: typeof graph.nodes, x: number): LayoutNode[] {
    const n = nodes.length
    return nodes.map((node, i) => ({
      id: node.id,
      x,
      y: n === 1 ? (PAD_TOP + PAD_BOT) / 2 : PAD_TOP + (i * (PAD_BOT - PAD_TOP)) / (n - 1),
      label: nodeDisplayLabel(node),
      nodeLabel: node.labels.find((l) => l !== 'Profile') ?? node.labels[0] ?? '',
      props: node as Record<string, unknown>,
    }))
  }

  return {
    nodes: [...tier(mutations, 100), ...tier(proteins, 370), ...tier(pathways, 640)],
    edges: graph.edges.filter((e) => e.type === 'AFFECTS' || e.type === 'INVOLVED_IN'),
  }
}

function nodeDisplayLabel(node: { labels: string[]; [k: string]: unknown }): string {
  if (node.labels.includes('Mutation'))
    return String(node.mutation_id ?? node.id).slice(0, 10)
  if (node.labels.includes('Protein'))
    return String(node.gene_symbol ?? node.kegg_gene_id ?? node.query ?? node.id).slice(0, 8)
  if (node.labels.includes('Pathway'))
    return String(node.name ?? node.kegg_id ?? node.id).slice(0, 10)
  return String(node.id).slice(0, 8)
}

const NODE_COLOR: Record<string, string> = {
  Mutation: '#64748b',
  Protein:  '#3b82f6',
  Pathway:  '#7c3aed',
}
const NODE_COLOR_DEFAULT = '#475569'

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

interface Props {
  profileId?: string | null
  highlights?: HydratedMutation[]
  showDynamic?: boolean
  selectedProtein?: string
  onDiveDeeper?: (card: ContextCard) => void
}

export default function PathwayGraph({ profileId, highlights: propHighlights = [], showDynamic = false, selectedProtein, onDiveDeeper }: Props) {
  const [hoveredNode, setHoveredNode] = useState<string | null>(null)
  const [clickedNode, setClickedNode] = useState<string | null>(null)
  const svgRef = useRef<SVGSVGElement>(null)

  const { graph, highlights: fetchedHighlights, loading: graphLoading } = useProfileGraph(profileId ?? null)

  // Backend highlights (from AFFECTS edges) take precedence when a profileId is set.
  // Fall back to prop highlights (in-memory SSE stream data) when no profileId.
  const highlights = profileId ? fetchedHighlights : propHighlights
  const highlightMap = Object.fromEntries(highlights.map((h) => [h.protein, h]))

  // Dynamic tiered view is opt-in; default is the static LUAD reference diagram
  // with backend highlights overlaid.
  const useDynamic = showDynamic && !!graph

  // Pre-compute dynamic layout once graph is available
  const dynamic = useDynamic ? computeLayout(graph) : null
  const dynNodeById = dynamic ? Object.fromEntries(dynamic.nodes.map((n) => [n.id, n])) : {}

  function handleNodeClick(id: string) {
    const opening = clickedNode !== id
    setClickedNode((prev) => (prev === id ? null : id))
    // A plain node click also sets the chat context (single active selection),
    // alongside the "Dive deeper with agent" button. Only protein nodes carry
    // metadata; outcome nodes just toggle the popover. Skip when toggling a node
    // closed so re-clicking to dismiss doesn't re-add context.
    const meta = PROTEIN_META[id]
    if (opening && meta && onDiveDeeper) {
      onDiveDeeper(buildContextCard(id, meta, highlightMap[id]))
    }
  }

  function svgToPercent(x: number, y: number) {
    return { left: `${(x / VIEWBOX_W) * 100}%`, top: `${(y / VIEWBOX_H) * 100}%` }
  }

  // ---- edge geometry helpers (shared) ----
  function circleEdgePoint(cx: number, cy: number, r: number, tx: number, ty: number) {
    const dx = tx - cx, dy = ty - cy
    const len = Math.sqrt(dx * dx + dy * dy) || 1
    return { x: cx + (dx / len) * r, y: cy + (dy / len) * r }
  }

  function arrowhead(ex: number, ey: number, ux: number, uy: number) {
    return `${ex},${ey} ${ex - ux * 7 - uy * 4},${ey - uy * 7 + ux * 4} ${ex - ux * 7 + uy * 4},${ey - uy * 7 - ux * 4}`
  }

  // ---- static graph helpers ----
  const staticNodeById    = Object.fromEntries(STATIC_NODES.map((n) => [n.id, n]))
  const outcomeById       = Object.fromEntries(OUTCOMES.map((o) => [o.id, o]))
  const popoverStaticNode  = !useDynamic && clickedNode ? staticNodeById[clickedNode] : null
  const popoverOutcomeNode = !useDynamic && clickedNode ? outcomeById[clickedNode] : null
  const staticAnchorX = popoverStaticNode?.x ?? popoverOutcomeNode?.x ?? 0
  const staticAnchorY = popoverStaticNode?.y ?? popoverOutcomeNode?.y ?? 0
  const staticMeta    = !useDynamic && clickedNode ? PROTEIN_META[clickedNode] : null
  const staticEffect  = !useDynamic && clickedNode ? highlightMap[clickedNode] : null

  // ---- dynamic popover ----
  const dynNode = useDynamic && clickedNode ? dynNodeById[clickedNode] : null
  const dynEffect = dynNode?.nodeLabel === 'Protein'
    ? (highlightMap[dynNode.label] ?? highlightMap[String(dynNode.props.gene_symbol ?? '')] ?? null)
    : null
  const dynAnchorX = dynNode?.x ?? 0
  const dynAnchorY = dynNode?.y ?? 0

  const popoverAnchorX = useDynamic ? dynAnchorX : staticAnchorX
  const popoverAnchorY = useDynamic ? dynAnchorY : staticAnchorY
  const flipLeft = popoverAnchorX > VIEWBOX_W / 2
  const flipUp   = popoverAnchorY > VIEWBOX_H * 0.6

  function buildContextCard(protein: string, effect?: HydratedMutation, pathway?: string): ContextCard {
    return {
      id: `${protein}-${Date.now()}`,
      protein,
      effect: (effect?.estimated_effect ?? 'no_effect') as EffectType,
      mutation_id: effect?.mutation_id ?? '',
      pathway,
    }
  }

  return (
    <div className="relative flex h-full w-full flex-col bg-slate-900">
      {/* Header */}
      <div className="flex flex-shrink-0 items-center justify-between border-b border-slate-700/60 px-4 py-2">
        <div className="flex items-center gap-2">
          <p className="text-xs font-semibold uppercase tracking-widest text-slate-400">
            {useDynamic ? 'Profile Subgraph' : 'Protein Pathway Network'}
          </p>
          {graphLoading && (
            <>
              <span className="h-3 w-3 animate-spin rounded-full border-2 border-slate-600 border-t-blue-400" />
              <span className="text-[10px] text-slate-500">loading highlights…</span>
            </>
          )}
          {!graphLoading && highlights.length > 0 && !useDynamic && (
            <span className="text-[10px] text-slate-500">
              {highlights.length} mutation{highlights.length !== 1 ? 's' : ''} highlighted
            </span>
          )}
          {useDynamic && dynamic && (
            <span className="text-[10px] text-slate-500">
              {dynamic.nodes.filter(n => n.nodeLabel === 'Mutation').length}m ·{' '}
              {dynamic.nodes.filter(n => n.nodeLabel === 'Protein').length}p ·{' '}
              {dynamic.nodes.filter(n => n.nodeLabel === 'Pathway').length}pw
            </span>
          )}
        </div>
        <div className="flex gap-4">
          {(useDynamic
            ? [['Mutation', '#64748b'], ['Protein', '#3b82f6'], ['Pathway', '#7c3aed']] as const
            : [['activating / GOF', '#f59e0b'], ['inactivating / LOF', '#ef4444'], ['uncertain', '#a78bfa']] as const
          ).map(([label, color]) => (
            <div key={label} className="flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-full" style={{ backgroundColor: color }} />
              <span className="text-[11px] capitalize text-slate-400">{label}</span>
            </div>
          ))}
        </div>
      </div>

      {/* SVG */}
      <div className="relative flex-1 overflow-hidden">
        <svg
          ref={svgRef}
          viewBox={`0 0 ${VIEWBOX_W} ${VIEWBOX_H}`}
          className="h-full w-full cursor-default"
          style={{ fontFamily: 'ui-monospace, monospace' }}
          onClick={(e) => { if ((e.target as SVGElement).tagName === 'svg') setClickedNode(null) }}
        >
          {useDynamic && dynamic ? (
            <>
              {/* Tier labels */}
              <text x={100} y={18} fontSize={9} fill="#475569" textAnchor="middle">Mutations</text>
              <text x={370} y={18} fontSize={9} fill="#475569" textAnchor="middle">Proteins</text>
              <text x={640} y={18} fontSize={9} fill="#475569" textAnchor="middle">Pathways</text>

              {/* Tier column backgrounds */}
              <rect x={60}  y={24} width={80}  height={VIEWBOX_H - 30} rx={8} fill="#1e293b" opacity={0.4} />
              <rect x={330} y={24} width={80}  height={VIEWBOX_H - 30} rx={8} fill="#1e293b" opacity={0.4} />
              <rect x={600} y={24} width={80}  height={VIEWBOX_H - 30} rx={8} fill="#1e293b" opacity={0.4} />

              {/* Edges */}
              {dynamic.edges.map((edge, i) => {
                const src = dynNodeById[edge.source]
                const tgt = dynNodeById[edge.target]
                if (!src || !tgt) return null

                const s = circleEdgePoint(src.x, src.y, NODE_R, tgt.x, tgt.y)
                const e2 = circleEdgePoint(tgt.x, tgt.y, NODE_R + 6, src.x, src.y)
                const dx = e2.x - s.x, dy = e2.y - s.y
                const len = Math.sqrt(dx * dx + dy * dy) || 1
                const ux = dx / len, uy = dy / len
                const lit = hoveredNode === edge.source || hoveredNode === edge.target
                          || clickedNode === edge.source || clickedNode === edge.target
                const stroke = lit ? '#64748b' : '#1e293b'
                const tip = { x: e2.x - ux * 6, y: e2.y - uy * 6 }

                return (
                  <g key={i}>
                    <line x1={s.x} y1={s.y} x2={tip.x} y2={tip.y}
                      stroke={stroke} strokeWidth={lit ? 1.5 : 1} />
                    <polygon points={arrowhead(e2.x, e2.y, ux, uy)} fill={stroke} />
                  </g>
                )
              })}

              {/* Nodes */}
              {dynamic.nodes.map((node) => {
                const isHover = hoveredNode === node.id
                const isClick = clickedNode === node.id
                const isSel   = node.label === selectedProtein
                const mutEffect = node.nodeLabel === 'Mutation'
                  ? (node.props.estimated_effect as string | undefined)
                  : undefined
                const protEffect = node.nodeLabel === 'Protein'
                  ? highlightMap[node.label] ?? highlightMap[String(node.props.gene_symbol ?? '')]
                  : undefined

                const baseColor = mutEffect
                  ? (effectNodeColor[mutEffect as EffectType] ?? effectNodeColor.uncertain)
                  : protEffect
                    ? (effectNodeColor[protEffect.estimated_effect] ?? effectNodeColor.uncertain)
                    : (NODE_COLOR[node.nodeLabel] ?? NODE_COLOR_DEFAULT)

                const glowColor = mutEffect
                  ? (effectGlow[mutEffect as EffectType] ?? effectGlow.uncertain)
                  : protEffect
                    ? (effectGlow[protEffect.estimated_effect] ?? effectGlow.uncertain)
                    : baseColor

                const r = isHover || isClick ? NODE_R + 3 : NODE_R
                const highlighted = !!mutEffect || !!protEffect

                return (
                  <g key={node.id} style={{ cursor: 'pointer' }}
                    onClick={(e) => { e.stopPropagation(); handleNodeClick(node.id) }}
                    onMouseEnter={() => setHoveredNode(node.id)}
                    onMouseLeave={() => setHoveredNode(null)}
                  >
                    {(highlighted || isHover || isClick || isSel) && (
                      <circle cx={node.x} cy={node.y} r={r + 8}
                        fill="none" stroke={glowColor} strokeWidth={isClick ? 2.5 : 1.5}
                        opacity={isClick ? 0.6 : 0.25} />
                    )}
                    {(isClick || isSel) && (
                      <circle cx={node.x} cy={node.y} r={r + 16}
                        fill="none" stroke={glowColor} strokeWidth={1} opacity={0.12} />
                    )}
                    <circle cx={node.x} cy={node.y} r={r}
                      fill={highlighted || isHover ? baseColor + '20' : '#0f172a'}
                      stroke={baseColor}
                      strokeWidth={isClick ? 2.5 : highlighted ? 2 : 1}
                    />
                    <text x={node.x} y={node.y + 1}
                      textAnchor="middle" dominantBaseline="middle"
                      fontSize={node.label.length > 6 ? 7 : 9}
                      fontWeight={highlighted || isHover ? '700' : '500'}
                      fill={highlighted ? baseColor : isHover ? '#cbd5e1' : '#64748b'}
                      style={{ pointerEvents: 'none', userSelect: 'none' }}
                    >
                      {node.label}
                    </text>
                  </g>
                )
              })}
            </>
          ) : (
            <>
              {/* Static region backgrounds */}
              <rect x="10"  y="32"  width="125" height="310" rx="8" fill="#1e293b" opacity="0.5" />
              <rect x="280" y="68"  width="345" height="55"  rx="6" fill="#1e293b" opacity="0.4" />
              <rect x="280" y="205" width="345" height="55"  rx="6" fill="#1e293b" opacity="0.4" />
              <rect x="280" y="300" width="345" height="58"  rx="6" fill="#1e293b" opacity="0.4" />
              <rect x="655" y="32"  width="110" height="340" rx="8" fill="#1e293b" opacity="0.35" />

              {PATHWAY_LABELS.map(({ label, x, y }) => (
                <text key={label} x={x} y={y} fontSize={9} fill="#475569" textAnchor="middle">{label}</text>
              ))}

              {/* Static edges */}
              {STATIC_EDGES.map((edge, i) => {
                const toOutcome = !!outcomeById[edge.to]
                const sn = staticNodeById[edge.from]
                const tn = toOutcome ? outcomeById[edge.to] : staticNodeById[edge.to]
                if (!sn || !tn) return null

                const tx = toOutcome ? tn.x - OUTCOME_W / 2 : tn.x
                const ty = tn.y
                const s = circleEdgePoint(sn.x, sn.y, NODE_R, tx, ty)

                let ex: number, ey: number
                if (toOutcome) {
                  ex = tx; ey = ty
                } else {
                  const ep = circleEdgePoint(tn.x, tn.y, NODE_R + 6, sn.x, sn.y)
                  ex = ep.x; ey = ep.y
                }

                const dx = ex - s.x, dy = ey - s.y
                const len = Math.sqrt(dx * dx + dy * dy) || 1
                const ux = dx / len, uy = dy / len
                const lit = highlightMap[edge.from] || highlightMap[edge.to]
                          || hoveredNode === edge.from || hoveredNode === edge.to
                          || clickedNode === edge.from || clickedNode === edge.to
                const stroke = lit ? '#64748b' : '#1e293b'
                const tip = { x: ex - ux * 6, y: ey - uy * 6 }

                return (
                  <g key={i}>
                    <line x1={s.x} y1={s.y} x2={tip.x} y2={tip.y}
                      stroke={stroke} strokeWidth={lit ? 1.5 : 1}
                      strokeDasharray={edge.inhibitory ? '4 3' : undefined}
                    />
                    {edge.inhibitory ? (
                      <line x1={tip.x - uy * 5} y1={tip.y + ux * 5}
                            x2={tip.x + uy * 5} y2={tip.y - ux * 5}
                        stroke={stroke} strokeWidth={2} />
                    ) : (
                      <polygon points={arrowhead(ex, ey, ux, uy)} fill={stroke} />
                    )}
                  </g>
                )
              })}

              {/* Static protein nodes */}
              {STATIC_NODES.map((node) => {
                const h       = highlightMap[node.id]
                const isHover = hoveredNode === node.id
                const isClick = clickedNode === node.id
                const isSel   = node.id === selectedProtein
                const baseColor = h ? effectNodeColor[h.estimated_effect] : (isHover ? '#94a3b8' : '#334155')
                const glowColor = h ? effectGlow[h.estimated_effect] : '#94a3b8'
                const r = isHover || isClick ? NODE_R + 3 : NODE_R
                return (
                  <g key={node.id} style={{ cursor: 'pointer' }}
                    onClick={(e) => { e.stopPropagation(); handleNodeClick(node.id) }}
                    onMouseEnter={() => setHoveredNode(node.id)}
                    onMouseLeave={() => setHoveredNode(null)}
                  >
                    {(h || isHover || isClick || isSel) && (
                      <circle cx={node.x} cy={node.y} r={r + 8}
                        fill="none" stroke={glowColor} strokeWidth={isClick ? 2.5 : 1.5}
                        opacity={isClick ? 0.6 : 0.25} />
                    )}
                    {(isClick || isSel) && (
                      <circle cx={node.x} cy={node.y} r={r + 16}
                        fill="none" stroke={glowColor} strokeWidth={1} opacity={0.12} />
                    )}
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

              {/* Outcome nodes */}
              {OUTCOMES.map((outcome) => {
                const isHover = hoveredNode === outcome.id
                const isClick = clickedNode === outcome.id
                const w = isHover || isClick ? OUTCOME_W + 6 : OUTCOME_W
                const h = isHover || isClick ? OUTCOME_H + 4 : OUTCOME_H
                return (
                  <g key={outcome.id} style={{ cursor: 'pointer' }}
                    onClick={(e) => { e.stopPropagation(); handleNodeClick(outcome.id) }}
                    onMouseEnter={() => setHoveredNode(outcome.id)}
                    onMouseLeave={() => setHoveredNode(null)}
                  >
                    {(isHover || isClick) && (
                      <rect x={outcome.x - w / 2 - 6} y={outcome.y - h / 2 - 6}
                        width={w + 12} height={h + 12} rx="10"
                        fill="none" stroke={outcome.color} strokeWidth={1.5}
                        opacity={isClick ? 0.5 : 0.2} />
                    )}
                    <rect x={outcome.x - w / 2} y={outcome.y - h / 2}
                      width={w} height={h} rx="6"
                      fill={isHover || isClick ? outcome.color + '22' : outcome.color + '12'}
                      stroke={outcome.color} strokeWidth={isClick ? 2 : 1.5}
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
            </>
          )}
        </svg>

        {/* ---- Dynamic popover ---- */}
        {useDynamic && dynNode && clickedNode && (
          <div
            className="pointer-events-auto absolute z-20 w-64 rounded-xl border border-slate-700 bg-slate-800 shadow-2xl"
            style={{
              ...svgToPercent(dynAnchorX, dynAnchorY),
              transform: `translate(${flipLeft ? 'calc(-100% - 12px)' : '12px'}, ${flipUp ? 'calc(-100% + 12px)' : '-50%'})`,
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-start justify-between px-4 pt-3 pb-2">
              <div>
                <p className="font-mono text-sm font-bold text-slate-100">{dynNode.label}</p>
                <p className="text-[10px] text-slate-500">{dynNode.nodeLabel}</p>
              </div>
              <button onClick={() => setClickedNode(null)}
                className="ml-2 mt-0.5 flex-shrink-0 rounded p-1 text-slate-500 hover:bg-slate-700 hover:text-slate-300"
              >
                <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            {/* Effect badge for Mutation nodes */}
            {dynNode.nodeLabel === 'Mutation' && dynNode.props.estimated_effect && (
              <div className="mx-3 mb-2 rounded-lg px-3 py-1.5"
                style={{
                  backgroundColor: (effectNodeColor[dynNode.props.estimated_effect as EffectType] ?? effectNodeColor.uncertain) + '18',
                  border: `1px solid ${(effectNodeColor[dynNode.props.estimated_effect as EffectType] ?? effectNodeColor.uncertain)}44`,
                }}
              >
                <div className="flex items-center gap-2">
                  <span className="h-1.5 w-1.5 rounded-full flex-shrink-0"
                    style={{ backgroundColor: effectNodeColor[dynNode.props.estimated_effect as EffectType] ?? effectNodeColor.uncertain }} />
                  <span className="text-xs font-semibold"
                    style={{ color: effectNodeColor[dynNode.props.estimated_effect as EffectType] ?? effectNodeColor.uncertain }}>
                    {effectLabel[dynNode.props.estimated_effect as EffectType] ?? String(dynNode.props.estimated_effect)}
                  </span>
                  {dynNode.props.confidence && (
                    <span className="ml-auto text-[10px] text-slate-400">{String(dynNode.props.confidence)} conf.</span>
                  )}
                </div>
              </div>
            )}

            {/* Effect badge for Protein nodes with a mutation */}
            {dynNode.nodeLabel === 'Protein' && dynEffect && (
              <div className="mx-3 mb-2 rounded-lg px-3 py-1.5"
                style={{
                  backgroundColor: (effectNodeColor[dynEffect.estimated_effect] ?? effectNodeColor.uncertain) + '18',
                  border: `1px solid ${effectNodeColor[dynEffect.estimated_effect] ?? effectNodeColor.uncertain}44`,
                }}
              >
                <div className="flex items-center gap-2">
                  <span className="h-1.5 w-1.5 rounded-full flex-shrink-0"
                    style={{ backgroundColor: effectNodeColor[dynEffect.estimated_effect] ?? effectNodeColor.uncertain }} />
                  <span className="text-xs font-semibold"
                    style={{ color: effectNodeColor[dynEffect.estimated_effect] ?? effectNodeColor.uncertain }}>
                    {effectLabel[dynEffect.estimated_effect] ?? dynEffect.estimated_effect}
                  </span>
                  <span className="ml-auto text-[10px] text-slate-400">{dynEffect.mutation_id}</span>
                </div>
              </div>
            )}

            {/* Key properties */}
            <div className="divide-y divide-slate-700/50 px-4 pb-3">
              {[
                ['Description', dynNode.props.kegg_description],
                ['KEGG Gene ID', dynNode.props.kegg_gene_id],
                ['UniProt', dynNode.props.uniprot_id],
                ['Pathway', dynNode.props.kegg_id ?? dynNode.props.name],
              ]
                .filter(([, v]) => v)
                .map(([label, val]) => (
                  <div key={String(label)} className="py-2">
                    <p className="text-[10px] font-medium uppercase tracking-wider text-slate-500">{label}</p>
                    <p className="mt-0.5 text-xs text-slate-300">{String(val)}</p>
                  </div>
                ))}

              {dynNode.nodeLabel === 'Protein' && onDiveDeeper && (
                <div className="pt-3">
                  <button
                    onClick={() => onDiveDeeper(buildContextCard(
                      dynNode.label,
                      dynEffect ?? undefined,
                      String(dynNode.props.kegg_description ?? ''),
                    ))}
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

        {/* ---- Static popover ---- */}
        {!useDynamic && (popoverStaticNode || popoverOutcomeNode) && staticMeta && (
          <div
            className="pointer-events-auto absolute z-20 w-64 rounded-xl border border-slate-700 bg-slate-800 shadow-2xl"
            style={{
              ...svgToPercent(staticAnchorX, staticAnchorY),
              transform: `translate(${flipLeft ? 'calc(-100% - 12px)' : '12px'}, ${flipUp ? 'calc(-100% + 12px)' : '-50%'})`,
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-start justify-between px-4 pt-3 pb-2">
              <div>
                <p className="font-mono text-base font-bold text-slate-100">{clickedNode}</p>
                <p className="text-[11px] text-slate-400 leading-tight">{staticMeta.fullName}</p>
              </div>
              <button onClick={() => setClickedNode(null)}
                className="ml-2 mt-0.5 flex-shrink-0 rounded p-1 text-slate-500 hover:bg-slate-700 hover:text-slate-300"
              >
                <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            {staticEffect && (
              <div className="mx-3 mb-2 rounded-lg px-3 py-1.5"
                style={{
                  backgroundColor: (effectNodeColor[staticEffect.estimated_effect] ?? effectNodeColor.uncertain) + '18',
                  border: `1px solid ${effectNodeColor[staticEffect.estimated_effect] ?? effectNodeColor.uncertain}44`,
                }}
              >
                <div className="flex items-center gap-2">
                  <span className="h-1.5 w-1.5 rounded-full flex-shrink-0"
                    style={{ backgroundColor: effectNodeColor[staticEffect.estimated_effect] ?? effectNodeColor.uncertain }} />
                  <span className="text-xs font-semibold"
                    style={{ color: effectNodeColor[staticEffect.estimated_effect] ?? effectNodeColor.uncertain }}>
                    {effectLabel[staticEffect.estimated_effect] ?? staticEffect.estimated_effect}
                  </span>
                  <span className="ml-auto text-[10px] text-slate-400">{staticEffect.mutation_id}</span>
                </div>
              </div>
            )}

            <div className="divide-y divide-slate-700/50 px-4 pb-3">
              {[
                ['Pathway',           staticMeta.pathway],
                ['Role',              staticMeta.role],
                ['Mechanism',         staticMeta.mechanism],
                ['Frequency in LUAD', staticMeta.frequency],
              ].map(([label, val]) => (
                <div key={label} className="py-2">
                  <p className="text-[10px] font-medium uppercase tracking-wider text-slate-500">{label}</p>
                  <p className="mt-0.5 text-xs text-slate-300">{val}</p>
                </div>
              ))}
              {staticMeta.drugs && (
                <div className="pt-2">
                  <p className="mb-1.5 text-[10px] font-medium uppercase tracking-wider text-slate-500">Targeted Agents</p>
                  <div className="flex flex-wrap gap-1">
                    {staticMeta.drugs.map((d) => (
                      <span key={d} className="rounded bg-slate-700 px-1.5 py-0.5 text-[10px] text-slate-300">{d}</span>
                    ))}
                  </div>
                </div>
              )}
              {popoverStaticNode && onDiveDeeper && clickedNode && (
                <div className="pt-3">
                  <button
                    onClick={() => onDiveDeeper(buildContextCard(clickedNode, staticEffect ?? undefined, staticMeta.pathway))}
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
