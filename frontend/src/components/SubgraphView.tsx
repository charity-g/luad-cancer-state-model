import type { Subgraph, SubgraphNode } from '../types'

// Renders the exact subgraph the agent traversed, in the dark SVG style of
// PathwayGraph. Auto-layout: ordered columns by node type
// (mutation -> gene -> pathway -> other). Only non-empty columns get space, so
// the picture spreads to fill the (narrow) chat panel and stays legible.

const KIND_ORDER = ['Mutation', 'Gene', 'Pathway', 'Compound', 'Disease']
const KIND_COL: Record<string, number> = { Mutation: 0, Gene: 1, Pathway: 2, Compound: 3, Disease: 3 }
const KIND_COLOR: Record<string, string> = {
  Mutation: '#ef4444', Gene: '#3b82f6', Pathway: '#22c55e', Compound: '#a855f7', Disease: '#64748b',
}
const COL_LABELS = ['Mutations', 'Genes', 'Pathways', 'Other']

const W = 560
const MARGIN_X = 80
const R = 22
const ROW = 84
const TOP = 64
const FS_NODE = 13   // node labels
const FS_PATH = 12   // pathway box text
const FS_EDGE = 11   // edge type labels
const FS_HEAD = 12   // column headers
const CHAR_W = 0.62  // monospace char width as fraction of font size

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
function pillWidth(text: string, fs: number): number {
  return text.length * fs * CHAR_W + 8
}

// Wrap a (possibly long) pathway name to lines of at most `maxChars`, breaking
// on spaces/underscores and hard-breaking any single token that is still too
// long, so the full name is shown inside its box instead of being clipped.
function wrapLabel(text: string, maxChars: number, maxLines: number): string[] {
  const lines: string[] = []
  let cur = ''
  const flush = () => { if (cur) { lines.push(cur); cur = '' } }
  for (let word of text.split(/[\s_]+/).filter(Boolean)) {
    while (word.length > maxChars) {
      flush()
      lines.push(word.slice(0, maxChars))
      word = word.slice(maxChars)
    }
    if (!cur) cur = word
    else if ((cur + ' ' + word).length <= maxChars) cur += ' ' + word
    else { flush(); cur = word }
  }
  flush()
  if (lines.length > maxLines) {
    const kept = lines.slice(0, maxLines)
    kept[maxLines - 1] = clip(kept[maxLines - 1], maxChars)
    return kept
  }
  return lines.length ? lines : [text]
}

// Dark rounded background so a label stays readable even when it lands near a
// line or another label.
function Pill({ x, y, text, fs, fill }: { x: number; y: number; text: string; fs: number; fill: string }) {
  const w = pillWidth(text, fs)
  return (
    <g>
      <rect x={x - w / 2} y={y - fs / 2 - 2} width={w} height={fs + 4} rx={3} fill="#0f172a" opacity={0.82} />
      <text x={x} y={y} fontSize={fs} fill={fill} textAnchor="middle" dominantBaseline="middle">{text}</text>
    </g>
  )
}

export default function SubgraphView(
  { subgraph, maxHeight = 460, fill = false }:
  { subgraph: Subgraph; maxHeight?: number; fill?: boolean },
) {
  // Bucket nodes into their type-columns, then keep only the non-empty ones so
  // they spread evenly across the available width.
  const buckets: SubgraphNode[][] = [[], [], [], []]
  for (const n of subgraph.nodes) buckets[colOf(n)].push(n)
  const used = buckets
    .map((arr, ci) => ({ arr, ci }))
    .filter((c) => c.arr.length > 0)

  const maxRows = Math.max(1, ...used.map((c) => c.arr.length))
  const H = TOP + maxRows * ROW
  const span = W - 2 * MARGIN_X
  const colX = (slot: number) =>
    used.length <= 1 ? W / 2 : MARGIN_X + (span * slot) / (used.length - 1)

  const pos: Record<string, { x: number; y: number }> = {}
  const headers: Array<{ x: number; label: string }> = []
  used.forEach((c, slot) => {
    const x = colX(slot)
    headers.push({ x, label: COL_LABELS[c.ci] })
    const colTop = TOP + ((maxRows - c.arr.length) * ROW) / 2
    c.arr.forEach((n, i) => {
      pos[n.id] = { x, y: colTop + i * ROW + ROW / 2 }
    })
  })

  const edges = subgraph.edges.filter(
    (e) => pos[e.source] && pos[e.target] && e.source !== e.target,
  )

  return (
    <div className={`overflow-hidden rounded-xl border border-slate-700 bg-slate-900 ${fill ? 'flex h-full w-full flex-col' : 'mt-2'}`}>
      <div className="flex flex-shrink-0 items-center justify-between border-b border-slate-700/60 px-3 py-1.5">
        <span className="text-[10px] font-semibold uppercase tracking-widest text-slate-400">
          Agent reasoning path
        </span>
        <div className="flex gap-3 text-[10px] text-slate-400">
          {KIND_ORDER.slice(0, 3).map((k) => (
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
        preserveAspectRatio="xMidYMid meet"
        className={fill ? 'min-h-0 w-full flex-1' : 'w-full'}
        style={fill ? { fontFamily: 'ui-monospace, monospace' } : { maxHeight, fontFamily: 'ui-monospace, monospace' }}
      >
        <defs>
          <marker id="sg-arrow" markerWidth="9" markerHeight="9" refX="7" refY="3" orient="auto">
            <path d="M0,0 L7,3 L0,6 Z" fill="#94a3b8" />
          </marker>
        </defs>

        {headers.map((h) => (
          <text key={h.label} x={h.x} y={30} fontSize={FS_HEAD} fill="#64748b" textAnchor="middle">{h.label}</text>
        ))}

        {edges.map((e, i) => {
          const s = pos[e.source], t = pos[e.target]
          const sameCol = Math.abs(s.x - t.x) < 1

          if (sameCol) {
            // Bow the edge out to the side so it doesn't run straight through the
            // stacked nodes in this column. Bow away from the nearer wall.
            const bow = (s.x > W / 2 ? -1 : 1) * 52
            const cx = s.x + bow, cy = (s.y + t.y) / 2
            const sd = Math.hypot(cx - s.x, cy - s.y) || 1
            const ed = Math.hypot(t.x - cx, t.y - cy) || 1
            const sx = s.x + ((cx - s.x) / sd) * R, sy = s.y + ((cy - s.y) / sd) * R
            const ex = t.x - ((t.x - cx) / ed) * (R + 9), ey = t.y - ((t.y - cy) / ed) * (R + 9)
            // Quadratic midpoint (t=0.5): 0.25*P0 + 0.5*C + 0.25*P2
            const lx = 0.25 * sx + 0.5 * cx + 0.25 * ex
            const ly = 0.25 * sy + 0.5 * cy + 0.25 * ey
            return (
              <g key={i}>
                <path d={`M${sx},${sy} Q${cx},${cy} ${ex},${ey}`} fill="none" stroke="#475569" strokeWidth={1.3} markerEnd="url(#sg-arrow)" />
                <Pill x={lx} y={ly} text={e.type} fs={FS_EDGE} fill="#94a3b8" />
              </g>
            )
          }

          const dx = t.x - s.x, dy = t.y - s.y
          const len = Math.hypot(dx, dy) || 1
          const ux = dx / len, uy = dy / len
          const x1 = s.x + ux * R, y1 = s.y + uy * R
          const x2 = t.x - ux * (R + 9), y2 = t.y - uy * (R + 9)
          // Stagger labels of near-parallel edges so they don't pile up.
          const f = i % 2 ? 0.40 : 0.60
          const lx = x1 + (x2 - x1) * f
          const ly = y1 + (y2 - y1) * f
          return (
            <g key={i}>
              <line x1={x1} y1={y1} x2={x2} y2={y2} stroke="#475569" strokeWidth={1.3} markerEnd="url(#sg-arrow)" />
              <Pill x={lx} y={ly} text={e.type} fs={FS_EDGE} fill="#94a3b8" />
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
            const lines = wrapLabel(name, 18, 3)
            const longest = Math.max(...lines.map((l) => l.length))
            const lineH = FS_PATH + 3
            // Fit the box to the text, but never let it run past the viewBox edge.
            const maxW = 2 * Math.min(p.x, W - p.x) - 8
            const w = Math.min(maxW, Math.max(80, longest * FS_PATH * CHAR_W + 16))
            const h = lines.length * lineH + 12
            const y0 = p.y - ((lines.length - 1) * lineH) / 2
            return (
              <g key={n.id}>
                <rect x={p.x - w / 2} y={p.y - h / 2} width={w} height={h} rx={7} fill={color + '22'} stroke={color} strokeWidth={1.4} />
                <text x={p.x} y={y0} fontSize={FS_PATH} fill={color} textAnchor="middle" dominantBaseline="middle">
                  {lines.map((ln, li) => (
                    <tspan key={li} x={p.x} dy={li === 0 ? 0 : lineH}>{ln}</tspan>
                  ))}
                </text>
              </g>
            )
          }
          return (
            <g key={n.id}>
              <circle cx={p.x} cy={p.y} r={R} fill={color + '22'} stroke={color} strokeWidth={1.7} />
              <Pill x={p.x} y={p.y + R + 12} text={clip(name, 16)} fs={FS_NODE} fill="#e2e8f0" />
            </g>
          )
        })}
      </svg>
    </div>
  )
}
