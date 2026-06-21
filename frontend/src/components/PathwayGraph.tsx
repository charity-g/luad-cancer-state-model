import { useState, useRef, useEffect, useMemo } from 'react'
import type { HydratedMutation, EffectType, ContextCard } from '../types'
import { useProfileGraph, type ProfileGraph } from '../hooks/useProfileGraph'
import { useProfilePPI } from '../hooks/useProfilePPI'

const VIEWBOX_W = 780
const VIEWBOX_H = 390
const NODE_R = 22

// ---------------------------------------------------------------------------
// Effect colour maps
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
// Synthetic graph from in-memory mutations
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
      nodes.push({ id: protId, labels: ['Protein'], gene_symbol: m.protein, query: m.protein })
    }
    edges.push({ source: m.mutation_id, target: protId, type: 'AFFECTS' })
  }
  return { nodes, edges }
}

// ---------------------------------------------------------------------------
// Layout types
// ---------------------------------------------------------------------------

interface LayoutNode {
  id: string
  x: number
  y: number
  label: string
  nodeLabel: string   // 'Mutation' | 'Protein' | 'Pathway' | 'PathwayMember' | 'PPISeed' | 'PPIMiddle' | 'PPIOutcome'
  props: Record<string, unknown>
  isMutated: boolean
  ppiOutcomeCat?: string
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

// ---------------------------------------------------------------------------
// Pathway layout (existing tiered layout)
// ---------------------------------------------------------------------------

function computeLayout(graph: ProfileGraph): { nodes: LayoutNode[]; edges: LayoutEdge[] } {
  const PAD_TOP = 40
  const PAD_BOT = 350

  const mutatedProteinIds = new Set(
    graph.edges.filter((e) => e.type === 'AFFECTS').map((e) => e.target)
  )

  const mutations      = graph.nodes.filter((n) => n.labels.includes('Mutation'))
  const directProteins = graph.nodes.filter((n) => n.labels.includes('Protein') && mutatedProteinIds.has(n.id))
  const pathways       = graph.nodes.filter((n) => n.labels.includes('Pathway'))
  const memberProteins = graph.nodes.filter((n) => n.labels.includes('Protein') && !mutatedProteinIds.has(n.id))

  const hasPathways = pathways.length > 0
  const hasMembers  = memberProteins.length > 0

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
      ...(hasPathways ? tier(pathways,           xs[2], 'Pathway')       : []),
      ...(hasMembers  ? tier(memberProteins, xs[3] ?? xs[2], 'PathwayMember') : []),
    ],
    edges: graph.edges.filter((e) => e.type === 'AFFECTS' || e.type === 'INVOLVED_IN'),
  }
}

// ---------------------------------------------------------------------------
// Merged PPI layout — mutation column on left + PPI radial on right
// ---------------------------------------------------------------------------

const PPI_CX    = 460
const PPI_R_SEED    = 80
const PPI_R_MIDDLE  = 155
const PPI_R_OUTCOME = 175

function computeMergedPPILayout(
  ppiGraph: ProfileGraph,
  graph: ProfileGraph,          // for mutation nodes
  highlightMap: Record<string, HydratedMutation>,
): { nodes: LayoutNode[]; edges: LayoutEdge[]; cx: number; cy: number; rSeed: number; rMiddle: number; rOutcome: number } {
  const CY = VIEWBOX_H / 2
  const MUT_X   = 70
  const PAD_TOP = 40
  const PAD_BOT = VIEWBOX_H - 40

  const mutationNodes = graph.nodes.filter((n) => n.labels.includes('Mutation'))
  const geneNodes     = ppiGraph.nodes.filter((n) => (n.labels ?? []).includes('Gene'))

  const seedNodes    = geneNodes.filter((n) => n.is_seed)
  const outcomeNodes = geneNodes.filter((n) => n.is_outcome && !n.is_seed)
  const middleNodes  = geneNodes.filter((n) => !n.is_seed && !n.is_outcome)

  function ringPositions(nodes: typeof geneNodes, R: number, angleOffset = 0) {
    return nodes.map((node, i) => {
      const angle = (2 * Math.PI * i) / Math.max(nodes.length, 1) + angleOffset - Math.PI / 2
      return { node, x: PPI_CX + R * Math.cos(angle), y: CY + R * Math.sin(angle) }
    })
  }

  // Fallback: if any ring is empty, lay all nodes in a single ring
  const hasTiers = seedNodes.length > 0 || outcomeNodes.length > 0
  let allPositions: Array<{ node: (typeof geneNodes)[0]; x: number; y: number; role: string }> = []

  if (hasTiers) {
    allPositions = [
      ...ringPositions(seedNodes,    PPI_R_SEED).map((p) => ({ ...p, role: 'PPISeed' })),
      ...ringPositions(middleNodes,  PPI_R_MIDDLE).map((p) => ({ ...p, role: 'PPIMiddle' })),
      ...ringPositions(outcomeNodes, PPI_R_OUTCOME).map((p) => ({ ...p, role: 'PPIOutcome' })),
    ]
  } else {
    const n = geneNodes.length
    allPositions = geneNodes.map((node, i) => {
      const angle = (2 * Math.PI * i) / Math.max(n, 1) - Math.PI / 2
      return { node, x: PPI_CX + PPI_R_MIDDLE * Math.cos(angle), y: CY + PPI_R_MIDDLE * Math.sin(angle), role: 'PPIMiddle' }
    })
  }

  // Mutation column (left)
  const mutLayout: LayoutNode[] = mutationNodes.map((m, i) => ({
    id: m.id,
    x: MUT_X,
    y: mutationNodes.length === 1
      ? CY
      : PAD_TOP + (i * (PAD_BOT - PAD_TOP)) / (mutationNodes.length - 1),
    label: String(m.mutation_id ?? m.id).slice(0, 10),
    nodeLabel: 'Mutation',
    props: m as Record<string, unknown>,
    isMutated: false,
  }))

  // PPI gene nodes
  const ppiLayout: LayoutNode[] = allPositions.map(({ node, x, y, role }) => {
    const sym = String(node.symbol ?? node.key ?? node.id)
    const outcomeCat = node.outcome_category as string | undefined
    return {
      id: node.id,
      x,
      y,
      label: sym.slice(0, 8),
      nodeLabel: role,
      props: node as Record<string, unknown>,
      isMutated: !!node.is_seed,
      ppiOutcomeCat: outcomeCat,
    }
  })

  // AFFECTS edges: mutation → matching seed protein
  const affectsEdges: LayoutEdge[] = []
  for (const mutNode of mutLayout) {
    const proteinName = String((mutNode.props as Record<string, unknown>).protein ?? '')
    const matchedSeed = allPositions.find(
      ({ node }) => String(node.symbol ?? node.key ?? node.id) === proteinName,
    )
    if (matchedSeed) {
      affectsEdges.push({ source: mutNode.id, target: matchedSeed.node.id, type: 'AFFECTS' })
    }
  }

  // PPI interaction edges
  const ppiEdges: LayoutEdge[] = ppiGraph.edges.map((e) => ({
    source: e.source, target: e.target, type: e.type,
  }))

  return {
    nodes: [...mutLayout, ...ppiLayout],
    edges: [...affectsEdges, ...ppiEdges],
    cx: PPI_CX,
    cy: CY,
    rSeed:    hasTiers ? PPI_R_SEED    : 0,
    rMiddle:  PPI_R_MIDDLE,
    rOutcome: hasTiers ? PPI_R_OUTCOME : 0,
  }
}

// ---------------------------------------------------------------------------
// Node / edge colours
// ---------------------------------------------------------------------------

const NODE_COLOR: Record<string, string> = {
  Mutation:      '#64748b',
  Protein:       '#3b82f6',
  Pathway:       '#7c3aed',
  PathwayMember: '#1d4ed8',
  PPISeed:       '#f59e0b',   // overridden by effect colour below
  PPIMiddle:     '#3b82f6',
  PPIOutcome:    '#22c55e',
}
const NODE_COLOR_DEFAULT = '#475569'

const PPI_EDGE_COLOR: Record<string, string> = {
  ACTIVATES:               '#22c55e',
  PHOSPHORYLATES:          '#f59e0b',
  INHIBITS:                '#ef4444',
  DEPHOSPHORYLATES:        '#fb923c',
  BINDS:                   '#3b82f6',
  REGULATES_EXPRESSION_OF: '#a78bfa',
  COMPONENT_OF:            '#64748b',
}
const PPI_EDGE_DEFAULT = '#475569'

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

interface Props {
  profileId?: string | null
  highlights?: HydratedMutation[]
  selectedProtein?: string
  ppiView?: boolean
  onDiveDeeper?: (card: ContextCard) => void
  onViewStructure?: (uniprotAc: string, proteinName: string, mutationResidue: number | null) => void
}

export default function PathwayGraph({
  profileId, highlights: propHighlights = [], selectedProtein,
  ppiView = false, onDiveDeeper, onViewStructure,
}: Props) {
  const [hoveredNode, setHoveredNode] = useState<string | null>(null)
  const [clickedNode, setClickedNode] = useState<string | null>(null)
  const [zoom, setZoom] = useState({ x: 0, y: 0, scale: 0.85 })
  const svgRef   = useRef<SVGSVGElement>(null)
  const dragStart = useRef<{ x: number; y: number; panX: number; panY: number } | null>(null)
  const didDrag   = useRef(false)

  // Non-passive wheel handler
  useEffect(() => {
    const el = svgRef.current
    if (!el) return
    const handler = (e: WheelEvent) => {
      e.preventDefault()
      const rect = el.getBoundingClientRect()
      const factor = e.deltaY < 0 ? 1.12 : 1 / 1.12
      setZoom((z) => {
        const newScale = Math.min(Math.max(z.scale * factor, 0.15), 6)
        const ratio    = newScale / z.scale
        const cVX = (e.clientX - rect.left) / rect.width  * VIEWBOX_W
        const cVY = (e.clientY - rect.top)  / rect.height * VIEWBOX_H
        return { x: cVX + (z.x - cVX) * ratio, y: cVY + (z.y - cVY) * ratio, scale: newScale }
      })
    }
    el.addEventListener('wheel', handler, { passive: false })
    return () => el.removeEventListener('wheel', handler)
  }, [])

  function handleSvgPointerDown(e: React.PointerEvent<SVGSVGElement>) {
    if ((e.target as SVGElement).tagName !== 'svg') return
    dragStart.current = { x: e.clientX, y: e.clientY, panX: zoom.x, panY: zoom.y }
    didDrag.current   = false
    ;(e.currentTarget as SVGSVGElement).setPointerCapture(e.pointerId)
  }

  function handleSvgPointerMove(e: React.PointerEvent<SVGSVGElement>) {
    if (!dragStart.current) return
    const dx = e.clientX - dragStart.current.x
    const dy = e.clientY - dragStart.current.y
    if (Math.abs(dx) > 3 || Math.abs(dy) > 3) didDrag.current = true
    const rect  = (e.currentTarget as SVGSVGElement).getBoundingClientRect()
    const svgDx = (dx / rect.width)  * VIEWBOX_W
    const svgDy = (dy / rect.height) * VIEWBOX_H
    const { panX, panY } = dragStart.current
    setZoom((z) => ({ ...z, x: panX + svgDx, y: panY + svgDy }))
  }

  function handleSvgPointerUp() { dragStart.current = null }
  function resetZoom()          { setZoom({ x: 0, y: 0, scale: 0.85 }) }

  // Data
  const { graph: backendGraph, highlights: fetchedHighlights, loading: graphLoading } = useProfileGraph(profileId ?? null)
  const { graph: ppiGraph, loading: ppiLoading } = useProfilePPI(ppiView && profileId ? profileId : null)

  const graph      = backendGraph ?? (propHighlights.length > 0 ? syntheticGraph(propHighlights) : null)
  const highlights = profileId ? fetchedHighlights : propHighlights
  const highlightMap = Object.fromEntries(highlights.map((h) => [h.protein, h]))

  // Compute layouts
  const pathwayLayout = useMemo(
    () => (graph && !ppiView ? computeLayout(graph) : null),
    [graph, ppiView],
  )
  const ppiMerged = useMemo(
    () => (ppiView && ppiGraph && graph ? computeMergedPPILayout(ppiGraph, graph, highlightMap) : null),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [ppiView, ppiGraph, graph],
  )

  // Active layout: PPI merged when in PPI mode, pathway otherwise
  const activeLayout = ppiMerged ?? pathwayLayout
  const nodeById     = activeLayout
    ? Object.fromEntries(activeLayout.nodes.map((n) => [n.id, n]))
    : {}

  function handleNodeClick(id: string) {
    setClickedNode((prev) => (prev === id ? null : id))
  }

  function svgToPercent(x: number, y: number) {
    return {
      left: `${((x * zoom.scale + zoom.x) / VIEWBOX_W) * 100}%`,
      top:  `${((y * zoom.scale + zoom.y) / VIEWBOX_H) * 100}%`,
    }
  }

  // Edge geometry
  function circleEdgePoint(cx: number, cy: number, r: number, tx: number, ty: number) {
    const dx = tx - cx, dy = ty - cy
    const len = Math.sqrt(dx * dx + dy * dy) || 1
    return { x: cx + (dx / len) * r, y: cy + (dy / len) * r }
  }

  function arrowhead(ex: number, ey: number, ux: number, uy: number) {
    return `${ex},${ey} ${ex - ux * 7 - uy * 4},${ey - uy * 7 + ux * 4} ${ex - ux * 7 + uy * 4},${ey - uy * 7 - ux * 4}`
  }

  // Popover anchor
  const clickedLayoutNode = clickedNode ? nodeById[clickedNode] : null
  const dynAnchorX = clickedLayoutNode?.x ?? 0
  const dynAnchorY = clickedLayoutNode?.y ?? 0
  const flipLeft   = dynAnchorX > VIEWBOX_W / 2
  const flipUp     = dynAnchorY > VIEWBOX_H * 0.6

  // Effect data for clicked protein / PPI seed node
  const clickedEffect = clickedLayoutNode
    ? (highlightMap[clickedLayoutNode.label] ??
       highlightMap[String(clickedLayoutNode.props.gene_symbol ?? clickedLayoutNode.props.symbol ?? '')] ??
       null)
    : null

  function buildContextCard(protein: string, effect?: HydratedMutation, pathway?: string): ContextCard {
    return {
      id: `${protein}-${Date.now()}`,
      protein,
      effect: (effect?.estimated_effect ?? 'no_effect') as EffectType,
      mutation_id: effect?.mutation_id ?? '',
      pathway,
    }
  }

  const useDynamic = !!activeLayout

  return (
    <div className="relative flex h-full w-full flex-col bg-slate-900">
      {/* Header */}
      <div className="flex flex-shrink-0 items-center justify-between border-b border-slate-700/60 px-4 py-2">
        <div className="flex items-center gap-2">
          <p className="text-xs font-semibold uppercase tracking-widest text-slate-400">
            {ppiView ? 'Signaling Cascade' : 'Protein Pathway Network'}
          </p>
          {/* Zoom controls */}
          <div className="flex items-center gap-0.5 rounded border border-slate-700 bg-slate-800">
            <button
              onClick={() => setZoom((z) => ({ ...z, scale: Math.min(z.scale * 1.25, 6) }))}
              className="rounded-l px-1.5 py-0.5 text-sm text-slate-400 transition-colors hover:bg-slate-700 hover:text-slate-200"
              title="Zoom in"
            >+</button>
            <button
              onClick={resetZoom}
              className="border-x border-slate-700 px-1.5 py-0.5 text-[10px] text-slate-500 transition-colors hover:bg-slate-700 hover:text-slate-300"
              title="Reset zoom"
            >{Math.round(zoom.scale * 100)}%</button>
            <button
              onClick={() => setZoom((z) => ({ ...z, scale: Math.max(z.scale / 1.25, 0.15) }))}
              className="rounded-r px-1.5 py-0.5 text-sm text-slate-400 transition-colors hover:bg-slate-700 hover:text-slate-200"
              title="Zoom out"
            >−</button>
          </div>
          {(graphLoading || ppiLoading) && (
            <>
              <span className="h-3 w-3 animate-spin rounded-full border-2 border-slate-600 border-t-blue-400" />
              <span className="text-[10px] text-slate-500">
                {ppiLoading ? 'loading interactions…' : 'loading profile graph…'}
              </span>
            </>
          )}
          {activeLayout && (
            <span className="text-[10px] text-slate-500">
              {activeLayout.nodes.filter((n) => n.nodeLabel === 'Mutation').length}m ·{' '}
              {activeLayout.nodes.filter((n) => ['Protein', 'PPISeed', 'PPIMiddle', 'PPIOutcome'].includes(n.nodeLabel)).length}p
              {!ppiView && ` · ${activeLayout.nodes.filter((n) => n.nodeLabel === 'Pathway').length}pw`}
            </span>
          )}
        </div>

        {/* Legend */}
        {(useDynamic || ppiView) && (
          <div className="flex flex-wrap gap-3">
            {ppiView ? (
              ([
                ['Mutations',    '#64748b'],
                ['Seed (mutated)', '#f59e0b'],
                ['Signaling',    '#3b82f6'],
                ['Activates',    '#22c55e'],
                ['Inhibits',     '#ef4444'],
                ['Outcome',      '#22c55e'],
              ] as const).map(([label, color]) => (
                <div key={label} className="flex items-center gap-1.5">
                  <span className="h-2 w-2 rounded-full" style={{ backgroundColor: color }} />
                  <span className="text-[10px] text-slate-400">{label}</span>
                </div>
              ))
            ) : profileId ? (
              ([
                ['Activating / GOF', '#f59e0b'],
                ['Inactivating / LOF', '#ef4444'],
                ['Uncertain',         '#a78bfa'],
                ['Pathway',           '#7c3aed'],
                ['Member',            '#1d4ed8'],
              ] as const).map(([label, color]) => (
                <div key={label} className="flex items-center gap-1.5">
                  <span className="h-2 w-2 rounded-full" style={{ backgroundColor: color }} />
                  <span className="text-[11px] text-slate-400">{label}</span>
                </div>
              ))
            ) : (
              ([['Mutation', '#64748b'], ['Protein', '#3b82f6']] as const).map(([label, color]) => (
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

        {/* Blank state */}
        {!ppiView && !graph && !graphLoading && (
          <div className="flex h-full flex-col items-center justify-center gap-3 text-center">
            <svg className="h-10 w-10 text-slate-700" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1}
                d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7" />
            </svg>
            <p className="text-sm text-slate-600">Upload a mutation profile or load a previous one to visualize pathways</p>
          </div>
        )}

        {/* PPI loading / empty */}
        {ppiView && ppiLoading && (
          <div className="flex h-full items-center justify-center gap-2 text-xs text-slate-400">
            <span className="h-3 w-3 animate-spin rounded-full border-2 border-slate-600 border-t-blue-400" />
            Loading interactions…
          </div>
        )}
        {ppiView && !ppiLoading && !ppiGraph && (
          <div className="flex h-full flex-col items-center justify-center gap-2 text-center">
            <p className="text-sm text-slate-500">No protein-protein interactions found</p>
            <p className="max-w-xs text-xs text-slate-600">
              KEGG interactions are available only for genes with recorded signal-flow edges between
              the mutated proteins in this profile.
            </p>
          </div>
        )}

        {/* Loading (pathway) */}
        {!ppiView && graphLoading && (
          <div className="flex h-full items-center justify-center">
            <span className="h-6 w-6 animate-spin rounded-full border-2 border-slate-700 border-t-blue-500" />
          </div>
        )}

        {/* ── Unified SVG ── */}
        <svg
          ref={svgRef}
          viewBox={`0 0 ${VIEWBOX_W} ${VIEWBOX_H}`}
          className={`h-full w-full ${!activeLayout ? 'hidden' : ''}`}
          style={{ fontFamily: 'ui-monospace, monospace', cursor: dragStart.current ? 'grabbing' : 'grab' }}
          onClick={(e) => { if ((e.target as SVGElement).tagName === 'svg' && !didDrag.current) setClickedNode(null) }}
          onPointerDown={handleSvgPointerDown}
          onPointerMove={handleSvgPointerMove}
          onPointerUp={handleSvgPointerUp}
        >
          <g transform={`translate(${zoom.x},${zoom.y}) scale(${zoom.scale})`}>

            {/* PPI guide rings + labels */}
            {ppiView && ppiMerged && (() => {
              const { cx, cy, rSeed, rMiddle, rOutcome } = ppiMerged
              return (
                <>
                  {rSeed > 0    && <circle cx={cx} cy={cy} r={rSeed}    fill="none" stroke="#334155" strokeWidth={1} strokeDasharray="4 4" opacity={0.5} />}
                  {rMiddle > 0  && <circle cx={cx} cy={cy} r={rMiddle}  fill="none" stroke="#334155" strokeWidth={1} strokeDasharray="4 4" opacity={0.4} />}
                  {rOutcome > 0 && <circle cx={cx} cy={cy} r={rOutcome} fill="none" stroke="#334155" strokeWidth={1} strokeDasharray="4 4" opacity={0.3} />}
                  {rSeed > 0    && <text x={cx} y={cy - rSeed - 6}    fontSize={8} fill="#475569" textAnchor="middle">seed (mutated)</text>}
                  {rOutcome > 0 && <text x={cx} y={cy - rOutcome - 6} fontSize={8} fill="#475569" textAnchor="middle">outcomes</text>}
                  {/* Column header for mutations */}
                  <text x={70} y={18} fontSize={9} fill="#475569" textAnchor="middle">Mutations</text>
                </>
              )
            })()}

            {/* Pathway tier backgrounds */}
            {!ppiView && activeLayout && (() => {
              const tierXs = [...new Set(activeLayout.nodes.map((n) => n.x))].sort((a, b) => a - b)
              const tierLabels: Record<number, string> = {}
              for (const n of activeLayout.nodes) {
                if (!tierLabels[n.x]) tierLabels[n.x] =
                  n.nodeLabel === 'Mutation'      ? 'Mutations'
                  : n.nodeLabel === 'Protein'     ? 'Proteins'
                  : n.nodeLabel === 'Pathway'     ? 'Pathways'
                  : 'Members'
              }
              return tierXs.map((x) => (
                <g key={x}>
                  <rect x={x - 40} y={24} width={80} height={VIEWBOX_H - 30} rx={8} fill="#1e293b" opacity={0.4} />
                  <text x={x} y={18} fontSize={9} fill="#475569" textAnchor="middle">{tierLabels[x]}</text>
                </g>
              ))
            })()}

            {/* Edges */}
            {activeLayout?.edges.map((edge, i) => {
              const src = nodeById[edge.source]
              const tgt = nodeById[edge.target]
              if (!src || !tgt) return null

              const isPpiEdge = edge.type !== 'AFFECTS' && edge.type !== 'INVOLVED_IN'
              const ppiColor  = isPpiEdge ? (PPI_EDGE_COLOR[edge.type] ?? PPI_EDGE_DEFAULT) : null

              const s   = circleEdgePoint(src.x, src.y, NODE_R, tgt.x, tgt.y)
              const e2  = circleEdgePoint(tgt.x, tgt.y, NODE_R + 6, src.x, src.y)
              const dx  = e2.x - s.x, dy = e2.y - s.y
              const len = Math.sqrt(dx * dx + dy * dy) || 1
              const ux  = dx / len, uy = dy / len
              const lit = hoveredNode === edge.source || hoveredNode === edge.target
                        || clickedNode === edge.source || clickedNode === edge.target

              if (isPpiEdge) {
                const ex = e2.x - ux * 6, ey = e2.y - uy * 6
                const mx = (s.x + ex) / 2, my = (s.y + ey) / 2
                return (
                  <g key={i}>
                    <line x1={s.x} y1={s.y} x2={ex} y2={ey}
                      stroke={ppiColor!} strokeWidth={lit ? 2 : 1.5} strokeOpacity={lit ? 0.9 : 0.55} />
                    <polygon points={arrowhead(e2.x, e2.y, ux, uy)} fill={ppiColor!} opacity={lit ? 0.9 : 0.7} />
                    {lit && (
                      <text x={mx} y={my - 3} fontSize={7} fill={ppiColor!} textAnchor="middle" opacity={0.9}>
                        {edge.type.replace(/_/g, ' ')}
                      </text>
                    )}
                  </g>
                )
              }

              const stroke = lit ? '#64748b' : '#1e293b'
              const tip    = { x: e2.x - ux * 6, y: e2.y - uy * 6 }
              return (
                <g key={i}>
                  <line x1={s.x} y1={s.y} x2={tip.x} y2={tip.y}
                    stroke={stroke} strokeWidth={lit ? 1.5 : 1} />
                  <polygon points={arrowhead(e2.x, e2.y, ux, uy)} fill={stroke} />
                </g>
              )
            })}

            {/* Nodes */}
            {activeLayout?.nodes.map((node) => {
              const isHover = hoveredNode === node.id
              const isClick = clickedNode === node.id
              const isSel   = node.label === selectedProtein

              // Effect colour logic
              const mutEffect = node.nodeLabel === 'Mutation'
                ? (node.props.estimated_effect as string | undefined)
                : undefined

              const protEffect =
                node.nodeLabel === 'Protein' && node.isMutated
                  ? (highlightMap[node.label] ?? highlightMap[String(node.props.gene_symbol ?? '')])
                  : node.nodeLabel === 'PPISeed'
                    ? (highlightMap[node.label] ??
                       highlightMap[String(node.props.gene_symbol ?? node.props.symbol ?? '')] ??
                       (node.props.estimated_effect
                         ? { estimated_effect: node.props.estimated_effect as EffectType } as HydratedMutation
                         : undefined))
                    : undefined

              // Outcome node colour
              const outcomeCat = node.ppiOutcomeCat
              const outcomeColor =
                node.nodeLabel === 'PPIOutcome'
                  ? (outcomeCat === 'apoptosis'        ? '#ef4444'
                    : outcomeCat === 'tumor_suppressor' ? '#a78bfa'
                    : '#22c55e')
                  : null

              const baseColor = mutEffect
                ? (effectNodeColor[mutEffect as EffectType] ?? effectNodeColor.uncertain)
                : protEffect
                  ? (effectNodeColor[protEffect.estimated_effect] ?? effectNodeColor.uncertain)
                  : outcomeColor
                    ?? (NODE_COLOR[node.nodeLabel] ?? NODE_COLOR_DEFAULT)

              const glowColor = mutEffect
                ? (effectGlow[mutEffect as EffectType] ?? effectGlow.uncertain)
                : protEffect
                  ? (effectGlow[protEffect.estimated_effect] ?? effectGlow.uncertain)
                  : baseColor

              const highlighted = !!mutEffect || !!protEffect || node.nodeLabel === 'PPIOutcome'
              const r = node.nodeLabel === 'PPISeed'    ? NODE_R + 4
                      : node.nodeLabel === 'PPIOutcome' ? NODE_R + 2
                      : NODE_R
              const rActive = isHover || isClick ? r + 3 : r

              return (
                <g key={node.id} style={{ cursor: 'pointer' }}
                  onClick={(e) => { e.stopPropagation(); handleNodeClick(node.id) }}
                  onMouseEnter={() => setHoveredNode(node.id)}
                  onMouseLeave={() => setHoveredNode(null)}
                >
                  {(highlighted || isHover || isClick || isSel) && (
                    <circle cx={node.x} cy={node.y} r={rActive + 8}
                      fill="none" stroke={glowColor} strokeWidth={isClick ? 2.5 : 1.5}
                      opacity={isClick ? 0.6 : 0.25} />
                  )}
                  {(isClick || isSel) && (
                    <circle cx={node.x} cy={node.y} r={rActive + 16}
                      fill="none" stroke={glowColor} strokeWidth={1} opacity={0.12} />
                  )}
                  <circle cx={node.x} cy={node.y} r={rActive}
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
                  {/* Essential-in-LUAD badge */}
                  {node.props.is_essential_luad === true && (
                    <circle cx={node.x + rActive - 4} cy={node.y - rActive + 4} r={4}
                      fill="#f43f5e" stroke="#1e293b" strokeWidth={1} />
                  )}
                </g>
              )
            })}
          </g>
        </svg>

        {/* ── Unified HTML popover ── */}
        {activeLayout && clickedLayoutNode && (
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
                <p className="font-mono text-sm font-bold text-slate-100">{clickedLayoutNode.label}</p>
                <p className="text-[10px] text-slate-500">{clickedLayoutNode.nodeLabel}</p>
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

            {/* Mutation effect badge */}
            {clickedLayoutNode.nodeLabel === 'Mutation' && clickedLayoutNode.props.estimated_effect && (
              <div className="mx-3 mb-2 rounded-lg px-3 py-1.5"
                style={{
                  backgroundColor: (effectNodeColor[clickedLayoutNode.props.estimated_effect as EffectType] ?? effectNodeColor.uncertain) + '18',
                  border: `1px solid ${(effectNodeColor[clickedLayoutNode.props.estimated_effect as EffectType] ?? effectNodeColor.uncertain)}44`,
                }}
              >
                <div className="flex items-center gap-2">
                  <span className="h-1.5 w-1.5 flex-shrink-0 rounded-full"
                    style={{ backgroundColor: effectNodeColor[clickedLayoutNode.props.estimated_effect as EffectType] ?? effectNodeColor.uncertain }} />
                  <span className="text-xs font-semibold"
                    style={{ color: effectNodeColor[clickedLayoutNode.props.estimated_effect as EffectType] ?? effectNodeColor.uncertain }}>
                    {effectLabel[clickedLayoutNode.props.estimated_effect as EffectType] ?? String(clickedLayoutNode.props.estimated_effect)}
                  </span>
                  {clickedLayoutNode.props.confidence && (
                    <span className="ml-auto text-[10px] text-slate-400">{String(clickedLayoutNode.props.confidence)} conf.</span>
                  )}
                </div>
              </div>
            )}

            {/* Protein / PPI seed effect badge */}
            {(['Protein', 'PPISeed'].includes(clickedLayoutNode.nodeLabel)) && clickedEffect && (
              <div className="mx-3 mb-2 rounded-lg px-3 py-1.5"
                style={{
                  backgroundColor: (effectNodeColor[clickedEffect.estimated_effect] ?? effectNodeColor.uncertain) + '18',
                  border: `1px solid ${effectNodeColor[clickedEffect.estimated_effect] ?? effectNodeColor.uncertain}44`,
                }}
              >
                <div className="flex items-center gap-2">
                  <span className="h-1.5 w-1.5 flex-shrink-0 rounded-full"
                    style={{ backgroundColor: effectNodeColor[clickedEffect.estimated_effect] ?? effectNodeColor.uncertain }} />
                  <span className="text-xs font-semibold"
                    style={{ color: effectNodeColor[clickedEffect.estimated_effect] ?? effectNodeColor.uncertain }}>
                    {effectLabel[clickedEffect.estimated_effect] ?? clickedEffect.estimated_effect}
                  </span>
                  {clickedEffect.mutation_id && (
                    <span className="ml-auto text-[10px] text-slate-400">{clickedEffect.mutation_id}</span>
                  )}
                </div>
              </div>
            )}

            {/* PPI outcome category badge */}
            {clickedLayoutNode.nodeLabel === 'PPIOutcome' && clickedLayoutNode.ppiOutcomeCat && (
              <div className="mx-3 mb-2 rounded-lg bg-slate-700/50 px-3 py-1.5">
                <p className="text-[10px] font-medium uppercase tracking-wider text-slate-400">Outcome</p>
                <p className="text-xs text-slate-200">{clickedLayoutNode.ppiOutcomeCat.replace(/_/g, ' ')}</p>
              </div>
            )}

            {/* Properties */}
            <div className="divide-y divide-slate-700/50 px-4 pb-3">
              {[
                ['Description',  clickedLayoutNode.props.kegg_description],
                ['KEGG Gene ID', clickedLayoutNode.props.kegg_gene_id],
                ['UniProt',      clickedLayoutNode.props.uniprot_id],
                ['Pathway',      clickedLayoutNode.props.kegg_id ?? clickedLayoutNode.props.name],
                // PPI-specific
                ['CRISPR score', typeof clickedLayoutNode.props.mean_crispr_effect_luad === 'number'
                  ? (clickedLayoutNode.props.mean_crispr_effect_luad as number).toFixed(3) : undefined],
                ['Dep. prob.',   typeof clickedLayoutNode.props.mean_dep_prob_luad === 'number'
                  ? (clickedLayoutNode.props.mean_dep_prob_luad as number).toFixed(2) : undefined],
              ]
                .filter(([, v]) => v !== undefined && v !== null && v !== '')
                .map(([label, val]) => (
                  <div key={String(label)} className="py-2">
                    <p className="text-[10px] font-medium uppercase tracking-wider text-slate-500">{label}</p>
                    <p className="mt-0.5 text-xs text-slate-300">{String(val)}</p>
                  </div>
                ))}

              {clickedLayoutNode.props.is_essential_luad === true && (
                <div className="py-2">
                  <p className="text-xs font-semibold text-rose-400">● Essential in LUAD</p>
                </div>
              )}

              {/* Action buttons — shown for any protein-like node */}
              {(['Protein', 'PPISeed', 'PPIMiddle', 'PPIOutcome'].includes(clickedLayoutNode.nodeLabel)) &&
                (onDiveDeeper || onViewStructure) && (
                <div className="space-y-2 pt-3">
                  {onDiveDeeper && (
                    <button
                      onClick={() => onDiveDeeper(buildContextCard(
                        clickedLayoutNode.label,
                        clickedEffect ?? undefined,
                        String(clickedLayoutNode.props.kegg_description ?? ''),
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
                  {onViewStructure && clickedLayoutNode.props.uniprot_id && (
                    <button
                      onClick={() => {
                        const uniprotAc = String(clickedLayoutNode.props.uniprot_id)
                        const name      = clickedLayoutNode.label
                        const hgvs      = clickedEffect?.hgvs_protein ?? null
                        const residue   = hgvs ? (parseInt((/(\d+)/.exec(hgvs) ?? [])[1] ?? '', 10) || null) : null
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
