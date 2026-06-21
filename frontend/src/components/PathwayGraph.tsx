import { useState, useRef } from 'react'
import type { HydratedMutation, EffectType, ContextCard } from '../types'
import { useProfileGraph, type ProfileGraph } from '../hooks/useProfileGraph'
import { useProfilePPI } from '../hooks/useProfilePPI'

const VIEWBOX_W = 780
const VIEWBOX_H = 390
const NODE_R = 22

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
// Synthetic graph — built from in-memory HydratedMutation list when no
// backend profileId is set. Gives a mutation→protein tiered view from the
// SSE stream data without a DB round-trip.
// ---------------------------------------------------------------------------

function syntheticGraph(mutations: HydratedMutation[]): ProfileGraph {
  const nodes: ProfileGraph['nodes'] = []
  const edges: ProfileGraph['edges'] = []
  const proteinSeen = new Set<string>()

  for (const m of mutations) {
    nodes.push({
      id: m.mutation_id,
      labels: ['Mutation'],
      mutation_id: m.mutation_id,
      estimated_effect: m.estimated_effect,
      confidence: m.confidence,
      protein: m.protein,
    })

    const protId = `prot:${m.protein}`
    if (!proteinSeen.has(protId)) {
      proteinSeen.add(protId)
      nodes.push({
        id: protId,
        labels: ['Protein'],
        gene_symbol: m.protein,
        query: m.protein,
      })
    }

    edges.push({ source: m.mutation_id, target: protId, type: 'AFFECTS' })
  }

  return { nodes, edges }
}

// ---------------------------------------------------------------------------
// Dynamic layout — tiered left-to-right from backend graph data
// ---------------------------------------------------------------------------

interface LayoutNode {
  id: string
  x: number
  y: number
  label: string
  nodeLabel: string   // Mutation | Protein | PathwayMember | Pathway
  props: Record<string, unknown>
  isMutated: boolean  // protein directly affected by a mutation via AFFECTS edge
}

interface LayoutEdge {
  source: string
  target: string
  type: string
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

function computeLayout(graph: ProfileGraph): { nodes: LayoutNode[]; edges: LayoutEdge[] } {
  const PAD_TOP = 40
  const PAD_BOT = 350

  // Protein ids directly hit by AFFECTS edges (the mutated proteins)
  const mutatedProteinIds = new Set(
    graph.edges.filter((e) => e.type === 'AFFECTS').map((e) => e.target)
  )

  const mutations       = graph.nodes.filter((n) => n.labels.includes('Mutation'))
  const directProteins  = graph.nodes.filter((n) => n.labels.includes('Protein') && mutatedProteinIds.has(n.id))
  const pathways        = graph.nodes.filter((n) => n.labels.includes('Pathway'))
  const memberProteins  = graph.nodes.filter((n) => n.labels.includes('Protein') && !mutatedProteinIds.has(n.id))

  const hasPathways = pathways.length > 0
  const hasMembers  = memberProteins.length > 0

  // Tier x-positions adapt to how many tiers are present
  const xs = hasPathways && hasMembers ? [70, 230, 470, 670]
    : hasPathways                      ? [100, 340, 640]
    :                                    [160, 600]

  function tier(nodes: typeof graph.nodes, x: number, label: string): LayoutNode[] {
    const n = nodes.length
    return nodes.map((node, i) => ({
      id: node.id,
      x,
      y: n === 1 ? (PAD_TOP + PAD_BOT) / 2 : PAD_TOP + (i * (PAD_BOT - PAD_TOP)) / (n - 1),
      label: nodeDisplayLabel(node),
      nodeLabel: label,
      props: node as Record<string, unknown>,
      isMutated: mutatedProteinIds.has(node.id),
    }))
  }

  return {
    nodes: [
      ...tier(mutations,      xs[0], 'Mutation'),
      ...tier(directProteins, xs[1], 'Protein'),
      ...(hasPathways ? tier(pathways,       xs[2], 'Pathway')       : []),
      ...(hasMembers  ? tier(memberProteins, xs[3] ?? xs[2], 'PathwayMember') : []),
    ],
    edges: graph.edges.filter((e) => e.type === 'AFFECTS' || e.type === 'INVOLVED_IN'),
  }
}

// Node-type base colours (used when highlights are off or node isn't mutated)
const NODE_COLOR: Record<string, string> = {
  Mutation:      '#64748b',
  Protein:       '#3b82f6',
  Pathway:       '#7c3aed',
  PathwayMember: '#1d4ed8',   // darker blue — pathway context proteins
}
const NODE_COLOR_DEFAULT = '#475569'

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

interface Props {
  profileId?: string | null
  highlights?: HydratedMutation[]   // in-memory mutations from SSE stream
  selectedProtein?: string
  onDiveDeeper?: (card: ContextCard) => void
  onViewStructure?: (uniprotAc: string, proteinName: string, mutationResidue: number | null) => void
}

// Edge colours for PPI interaction types
const PPI_EDGE_COLOR: Record<string, string> = {
  ACTIVATES:                '#22c55e',   // green
  PHOSPHORYLATES:           '#f59e0b',   // amber
  INHIBITS:                 '#ef4444',   // red
  DEPHOSPHORYLATES:         '#fb923c',   // orange
  BINDS:                    '#3b82f6',   // blue
  REGULATES_EXPRESSION_OF:  '#a78bfa',   // purple
  COMPONENT_OF:             '#64748b',   // slate
}
const PPI_EDGE_DEFAULT = '#475569'

export default function PathwayGraph({ profileId, highlights: propHighlights = [], selectedProtein, onDiveDeeper, onViewStructure }: Props) {
  const [hoveredNode, setHoveredNode] = useState<string | null>(null)
  const [clickedNode, setClickedNode] = useState<string | null>(null)
  const [ppiView, setPpiView] = useState(false)
  const svgRef = useRef<SVGSVGElement>(null)

  const { graph: backendGraph, highlights: fetchedHighlights, loading: graphLoading } = useProfileGraph(profileId ?? null)
  const { graph: ppiGraph, loading: ppiLoading } = useProfilePPI(ppiView && profileId ? profileId : null)

  // Source of truth priority:
  //   1. Backend profile graph (when profileId set + highlights on)
  //   2. Synthetic graph from in-memory SSE mutations (highlights off, but analysis ran)
  //   3. Blank (no data yet)
  const graph = backendGraph ?? (propHighlights.length > 0 ? syntheticGraph(propHighlights) : null)
  const highlights = profileId ? fetchedHighlights : propHighlights
  const highlightMap = Object.fromEntries(highlights.map((h) => [h.protein, h]))

  const useDynamic = !!graph

  const dynamic = useDynamic ? computeLayout(graph!) : null
  const dynNodeById = dynamic ? Object.fromEntries(dynamic.nodes.map((n) => [n.id, n])) : {}

  function handleNodeClick(id: string) {
    setClickedNode((prev) => (prev === id ? null : id))
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

  // ---- dynamic popover ----
  const dynNode = clickedNode ? dynNodeById[clickedNode] : null
  const dynEffect = dynNode?.nodeLabel === 'Protein'
    ? (highlightMap[dynNode.label] ?? highlightMap[String(dynNode.props.gene_symbol ?? '')] ?? null)
    : null
  const dynAnchorX = dynNode?.x ?? 0
  const dynAnchorY = dynNode?.y ?? 0
  const flipLeft = dynAnchorX > VIEWBOX_W / 2
  const flipUp   = dynAnchorY > VIEWBOX_H * 0.6

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
            {ppiView ? 'Protein Interactions' : 'Protein Pathway Network'}
          </p>
          {/* PPI toggle — only shown when highlights are on (profileId set) */}
          {profileId && (
            <button
              onClick={() => { setPpiView(v => !v); setClickedNode(null) }}
              className={`rounded px-2 py-0.5 text-[10px] font-medium transition-colors ${
                ppiView
                  ? 'bg-blue-700 text-blue-100'
                  : 'bg-slate-800 text-slate-400 hover:bg-slate-700 hover:text-slate-200'
              }`}
            >
              {ppiView ? 'PPI on' : 'PPI'}
            </button>
          )}
          {graphLoading && (
            <>
              <span className="h-3 w-3 animate-spin rounded-full border-2 border-slate-600 border-t-blue-400" />
              <span className="text-[10px] text-slate-500">loading profile graph…</span>
            </>
          )}
          {useDynamic && dynamic && (
            <span className="text-[10px] text-slate-500">
              {dynamic.nodes.filter(n => n.nodeLabel === 'Mutation').length}m ·{' '}
              {dynamic.nodes.filter(n => n.nodeLabel === 'Protein').length}p ·{' '}
              {dynamic.nodes.filter(n => n.nodeLabel === 'Pathway').length}pw ·{' '}
              {dynamic.nodes.filter(n => n.nodeLabel === 'PathwayMember').length} members
            </span>
          )}
        </div>
        {(useDynamic || ppiView) && (
          <div className="flex flex-wrap gap-3">
            {ppiView ? (
              // PPI view — show interaction type colours
              Object.entries(PPI_EDGE_COLOR).map(([rel, color]) => (
                <div key={rel} className="flex items-center gap-1.5">
                  <span className="h-0.5 w-4 rounded" style={{ backgroundColor: color }} />
                  <span className="text-[10px] text-slate-400">{rel.replace(/_/g, ' ')}</span>
                </div>
              ))
            ) : profileId ? (
              ([
                ['Activating / GOF', '#f59e0b'],
                ['Inactivating / LOF', '#ef4444'],
                ['Uncertain', '#a78bfa'],
                ['Pathway', '#7c3aed'],
                ['Member', '#1d4ed8'],
              ] as const).map(([label, color]) => (
                <div key={label} className="flex items-center gap-1.5">
                  <span className="h-2 w-2 rounded-full" style={{ backgroundColor: color }} />
                  <span className="text-[11px] text-slate-400">{label}</span>
                </div>
              ))
            ) : (
              ([
                ['Mutation', '#64748b'],
                ['Protein', '#3b82f6'],
              ] as const).map(([label, color]) => (
                <div key={label} className="flex items-center gap-1.5">
                  <span className="h-2 w-2 rounded-full" style={{ backgroundColor: color }} />
                  <span className="text-[11px] text-slate-400">{label}</span>
                </div>
              ))
            )}
          </div>
        )}
      </div>

      {/* Canvas */}
      <div className="relative flex-1 overflow-hidden">

        {/* ── PPI network view ──────────────────────────────────────── */}
        {ppiView && (
          <div className="absolute inset-0 flex flex-col">
            {ppiLoading && (
              <div className="flex flex-1 items-center justify-center gap-2 text-xs text-slate-400">
                <span className="h-3 w-3 animate-spin rounded-full border-2 border-slate-600 border-t-blue-400" />
                Loading interactions…
              </div>
            )}
            {!ppiLoading && !ppiGraph && (
              <div className="flex flex-1 flex-col items-center justify-center gap-2 text-center">
                <p className="text-sm text-slate-500">No protein-protein interactions found</p>
                <p className="max-w-xs text-xs text-slate-600">
                  KEGG interactions are available only for genes with recorded signal-flow edges
                  between the mutated proteins in this profile.
                </p>
              </div>
            )}
            {!ppiLoading && ppiGraph && (() => {
              // Circular layout — all gene nodes arranged on a circle
              const geneNodes = ppiGraph.nodes.filter(n => (n.labels ?? []).includes('Gene'))
              const n = geneNodes.length
              const cx = VIEWBOX_W / 2, cy = VIEWBOX_H / 2
              const R = Math.min(cx, cy) - 60
              const pos = new Map(geneNodes.map((node, i) => {
                const angle = (2 * Math.PI * i) / n - Math.PI / 2
                return [node.id, { x: cx + R * Math.cos(angle), y: cy + R * Math.sin(angle) }]
              }))
              return (
                <svg
                  viewBox={`0 0 ${VIEWBOX_W} ${VIEWBOX_H}`}
                  className="h-full w-full"
                  ref={svgRef}
                >
                  {/* Edges */}
                  {ppiGraph.edges.map((edge, i) => {
                    const s = pos.get(edge.source), t = pos.get(edge.target)
                    if (!s || !t) return null
                    const color = PPI_EDGE_COLOR[edge.type] ?? PPI_EDGE_DEFAULT
                    const dx = t.x - s.x, dy = t.y - s.y
                    const len = Math.sqrt(dx * dx + dy * dy) || 1
                    const ux = dx / len, uy = dy / len
                    const ex = t.x - ux * NODE_R, ey = t.y - uy * NODE_R
                    const sx = s.x + ux * NODE_R, sy = s.y + uy * NODE_R
                    return (
                      <g key={i}>
                        <line x1={sx} y1={sy} x2={ex} y2={ey}
                          stroke={color} strokeWidth={1.5} strokeOpacity={0.7} />
                        <polygon
                          points={`${ex},${ey} ${ex - ux * 7 - uy * 4},${ey - uy * 7 + ux * 4} ${ex - ux * 7 + uy * 4},${ey - uy * 7 - ux * 4}`}
                          fill={color} opacity={0.8} />
                        {/* Edge type label on mid-point */}
                        <text
                          x={(sx + ex) / 2} y={(sy + ey) / 2 - 3}
                          fontSize={7} fill={color} textAnchor="middle" opacity={0.9}
                        >
                          {edge.type.replace(/_/g, ' ')}
                        </text>
                      </g>
                    )
                  })}
                  {/* Nodes */}
                  {geneNodes.map((node) => {
                    const p = pos.get(node.id)
                    if (!p) return null
                    const sym = String(node.symbol ?? node.key ?? node.id).slice(0, 8)
                    const eff = node.estimated_effect as string | undefined
                    const fillColor = eff
                      ? (effectNodeColor[eff as EffectType] ?? '#3b82f6')
                      : '#3b82f6'
                    const isHov = hoveredNode === node.id
                    const isSel = clickedNode === node.id
                    return (
                      <g key={node.id}
                        style={{ cursor: 'pointer' }}
                        onMouseEnter={() => setHoveredNode(node.id)}
                        onMouseLeave={() => setHoveredNode(null)}
                        onClick={() => setClickedNode(prev => prev === node.id ? null : node.id)}
                      >
                        {(isHov || isSel) && (
                          <circle cx={p.x} cy={p.y} r={NODE_R + 5}
                            fill={fillColor} opacity={0.15} />
                        )}
                        <circle cx={p.x} cy={p.y} r={isHov || isSel ? NODE_R + 2 : NODE_R}
                          fill={fillColor} stroke={isSel ? '#fff' : '#1e293b'} strokeWidth={isSel ? 2 : 1} />
                        <text x={p.x} y={p.y + 1} textAnchor="middle" dominantBaseline="middle"
                          fontSize={9} fontWeight={600} fill="#fff">
                          {sym}
                        </text>
                        {/* Essentiality badge */}
                        {node.is_essential_luad === true && (
                          <circle cx={p.x + NODE_R - 4} cy={p.y - NODE_R + 4} r={4}
                            fill="#f43f5e" stroke="#1e293b" strokeWidth={1} />
                        )}
                      </g>
                    )
                  })}
                  {/* Clicked gene popover */}
                  {clickedNode && (() => {
                    const node = ppiGraph.nodes.find(n => n.id === clickedNode)
                    const p = pos.get(clickedNode)
                    if (!node || !p) return null
                    const flipLeft = p.x > VIEWBOX_W / 2
                    const flipUp   = p.y > VIEWBOX_H * 0.6
                    const popX = flipLeft ? p.x - NODE_R - 8 : p.x + NODE_R + 8
                    const popY = flipUp   ? p.y - 8 : p.y + 8
                    const sym = String(node.symbol ?? node.key ?? node.id)
                    const eff = node.estimated_effect as string | undefined
                    const crispr = node.mean_crispr_effect_luad as number | undefined
                    const dep = node.mean_dep_prob_luad as number | undefined
                    return (
                      <foreignObject
                        x={flipLeft ? popX - 160 : popX}
                        y={flipUp ? popY - 120 : popY}
                        width={168} height={124}
                      >
                        <div className="rounded-lg border border-slate-600 bg-slate-800 p-2.5 text-[11px] shadow-xl">
                          <p className="mb-1 font-mono font-semibold text-slate-100">{sym}</p>
                          {eff && <p className="text-slate-400">Effect: <span className="text-slate-200">{eff.replace(/_/g, ' ')}</span></p>}
                          {crispr !== undefined && <p className="text-slate-400">CRISPR: <span className="text-slate-200">{crispr.toFixed(3)}</span></p>}
                          {dep !== undefined && <p className="text-slate-400">Dep prob: <span className="text-slate-200">{dep.toFixed(2)}</span></p>}
                          {node.is_essential_luad === true && <p className="mt-1 text-rose-400">● Essential in LUAD</p>}
                        </div>
                      </foreignObject>
                    )
                  })()}
                </svg>
              )
            })()}
          </div>
        )}

        {/* ── Pathway / synthetic view (hidden when PPI is on) ───────── */}
        {/* Blank state — no data at all */}
        {!ppiView && !graph && !graphLoading && (
          <div className="flex h-full flex-col items-center justify-center gap-3 text-center">
            <svg className="h-10 w-10 text-slate-700" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1}
                d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7" />
            </svg>
            <p className="text-sm text-slate-600">Upload a mutation profile or load a previous one to visualize pathways</p>
          </div>
        )}

        {/* Loading state */}
        {!ppiView && graphLoading && (
          <div className="flex h-full items-center justify-center">
            <span className="h-6 w-6 animate-spin rounded-full border-2 border-slate-700 border-t-blue-500" />
          </div>
        )}

        {/* Dynamic graph */}
        <svg
          ref={svgRef}
          viewBox={`0 0 ${VIEWBOX_W} ${VIEWBOX_H}`}
          className={`h-full w-full cursor-default ${!useDynamic || ppiView ? 'hidden' : ''}`}
          style={{ fontFamily: 'ui-monospace, monospace' }}
          onClick={(e) => { if ((e.target as SVGElement).tagName === 'svg') setClickedNode(null) }}
        >
          {useDynamic && dynamic ? (
            <>
              {/* Tier labels + column backgrounds — derived from actual layout */}
              {dynamic.nodes.length > 0 && (() => {
                const tierXs = [...new Set(dynamic.nodes.map(n => n.x))].sort((a, b) => a - b)
                const tierLabels: Record<number, string> = {}
                for (const n of dynamic.nodes) {
                  if (!tierLabels[n.x]) tierLabels[n.x] =
                    n.nodeLabel === 'Mutation'      ? 'Mutations'
                    : n.nodeLabel === 'Protein'     ? 'Proteins'
                    : n.nodeLabel === 'Pathway'     ? 'Pathways'
                    : 'Members'
                }
                return tierXs.map(x => (
                  <g key={x}>
                    <rect x={x - 40} y={24} width={80} height={VIEWBOX_H - 30} rx={8} fill="#1e293b" opacity={0.4} />
                    <text x={x} y={18} fontSize={9} fill="#475569" textAnchor="middle">{tierLabels[x]}</text>
                  </g>
                ))
              })()}

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

                // Effect colours only apply when highlights are on (profileId set)
                const mutEffect = profileId && node.nodeLabel === 'Mutation'
                  ? (node.props.estimated_effect as string | undefined)
                  : undefined
                const protEffect = profileId && node.nodeLabel === 'Protein' && node.isMutated
                  ? (highlightMap[node.label] ?? highlightMap[String(node.props.gene_symbol ?? '')])
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
          ) : null}
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

              {dynNode.nodeLabel === 'Protein' && (onDiveDeeper || onViewStructure) && (
                <div className="space-y-2 pt-3">
                  {onDiveDeeper && (
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
                  )}
                  {onViewStructure && dynNode.props.uniprot_id && (
                    <button
                      onClick={() => {
                        const uniprotAc = String(dynNode.props.uniprot_id)
                        const name = dynNode.label
                        const hgvs = dynEffect?.hgvs_protein ?? null
                        const residueMatch = hgvs ? /(\d+)/.exec(hgvs) : null
                        const residue = residueMatch ? parseInt(residueMatch[1], 10) : null
                        onViewStructure(uniprotAc, name, residue)
                        setClickedNode(null)
                      }}
                      className="flex w-full items-center justify-center gap-2 rounded-lg border border-slate-600 bg-slate-800 px-3 py-2 text-xs font-semibold text-slate-300 transition-colors hover:border-slate-500 hover:bg-slate-700"
                    >
                      <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                          d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z" />
                      </svg>
                      View 3D structure
                    </button>
                  )}
                </div>
              )}
            </div>
          </div>
        )}

      </div>
    </div>
  )
}
