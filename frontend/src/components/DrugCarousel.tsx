import { useRef } from 'react'
import type { ProfileDrug } from '../hooks/useProfileDrugs'
import type { ContextCard, EffectType } from '../types'

const STATUS_STYLE: Record<string, { bg: string; text: string; border: string }> = {
  approved:       { bg: 'bg-emerald-900/50', text: 'text-emerald-300', border: 'border-emerald-700' },
  clinical_trial: { bg: 'bg-amber-900/50',   text: 'text-amber-300',   border: 'border-amber-700'   },
  experimental:   { bg: 'bg-slate-800',       text: 'text-slate-400',   border: 'border-slate-600'   },
}
const STATUS_DEFAULT = { bg: 'bg-slate-800', text: 'text-slate-400', border: 'border-slate-600' }

function statusStyle(s: string | undefined) {
  if (!s) return STATUS_DEFAULT
  const key = s.toLowerCase().replace(/\s+/g, '_')
  return STATUS_STYLE[key] ?? STATUS_DEFAULT
}

interface Props {
  drugs: ProfileDrug[]
  loading: boolean
  fallbackDrugs: ProfileDrug[]  // drugs from chat messages when graph has none yet
  onSelect: (card: ContextCard) => void
  onClose: () => void
}

export default function DrugCarousel({ drugs, loading, fallbackDrugs, onSelect, onClose }: Props) {
  const scrollRef = useRef<HTMLDivElement>(null)

  const displayDrugs = drugs.length > 0 ? drugs : fallbackDrugs

  // Dedupe by drugbank_id or drug_name
  const seen = new Set<string>()
  const unique = displayDrugs.filter((d) => {
    const k = d.drugbank_id || d.drug_name
    if (seen.has(k)) return false
    seen.add(k)
    return true
  })

  function handleSelect(d: ProfileDrug) {
    onSelect({
      id: `drug-${d.drugbank_id || d.drug_name}-${Date.now()}`,
      protein: d.gene_symbol,
      effect: (d.estimated_effect ?? 'uncertain') as EffectType,
      mutation_id: d.mutation_id ?? '',
      pathway: d.drug_name,
    })
    onClose()
  }

  function scroll(dir: 'left' | 'right') {
    scrollRef.current?.scrollBy({ left: dir === 'right' ? 220 : -220, behavior: 'smooth' })
  }

  return (
    <div className="absolute left-0 right-0 top-full z-30 border-b border-slate-700 bg-slate-900 shadow-2xl">
      <div className="flex items-center justify-between px-4 py-2">
        <span className="text-[10px] font-semibold uppercase tracking-widest text-slate-500">
          {drugs.length > 0
            ? 'Drugs targeting mutated proteins in this profile'
            : fallbackDrugs.length > 0
              ? 'Drugs from recent queries'
              : ''}
        </span>
        <button
          onClick={onClose}
          className="rounded p-0.5 text-slate-500 hover:bg-slate-800 hover:text-slate-300 transition-colors"
        >
          <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      {loading && (
        <div className="flex items-center gap-2 px-4 pb-3 text-xs text-slate-500">
          <span className="h-3 w-3 animate-spin rounded-full border-2 border-slate-600 border-t-blue-400" />
          Loading drugs…
        </div>
      )}

      {!loading && unique.length === 0 && (
        <p className="px-4 pb-3 text-xs text-slate-600">
          No drugs stored yet — ask the agent a drug question to populate this panel.
        </p>
      )}

      {!loading && unique.length > 0 && (
        <div className="relative flex items-center">
          {/* Left scroll */}
          <button
            onClick={() => scroll('left')}
            className="absolute left-0 z-10 flex h-full items-center bg-gradient-to-r from-slate-900 to-transparent px-1.5 text-slate-400 hover:text-slate-200"
          >
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
          </button>

          <div
            ref={scrollRef}
            className="flex gap-3 overflow-x-auto px-8 pb-3 pt-1 scrollbar-none"
            style={{ scrollbarWidth: 'none', msOverflowStyle: 'none' }}
          >
            {unique.map((d, i) => {
              const st = statusStyle(d.approval_status)
              return (
                <button
                  key={`${d.drugbank_id || d.drug_name}-${i}`}
                  onClick={() => handleSelect(d)}
                  className={`flex w-48 flex-shrink-0 flex-col gap-1.5 rounded-xl border p-3 text-left transition-all hover:scale-[1.02] hover:shadow-lg ${st.border} ${st.bg}`}
                >
                  {/* Drug name */}
                  <p className="truncate text-sm font-bold capitalize text-slate-100">
                    {d.drug_name}
                  </p>

                  {/* Target gene chip */}
                  <div className="flex items-center gap-1.5">
                    <span className="rounded bg-slate-700 px-1.5 py-0.5 font-mono text-[10px] font-semibold text-slate-300">
                      {d.gene_symbol}
                    </span>
                    {d.drugbank_id && (
                      <span className="text-[9px] text-slate-600">{d.drugbank_id}</span>
                    )}
                  </div>

                  {/* Approval badge */}
                  <span className={`self-start rounded-full px-2 py-0.5 text-[10px] font-medium ${st.text}`}>
                    {d.approval_status || 'unknown'}
                  </span>

                  {/* Mechanism */}
                  {d.mechanism && (
                    <p className="line-clamp-2 text-[10px] leading-snug text-slate-500">
                      {d.mechanism}
                    </p>
                  )}

                  <p className="mt-auto text-[9px] text-slate-600">Click to set context →</p>
                </button>
              )
            })}
          </div>

          {/* Right scroll */}
          <button
            onClick={() => scroll('right')}
            className="absolute right-0 z-10 flex h-full items-center bg-gradient-to-l from-slate-900 to-transparent px-1.5 text-slate-400 hover:text-slate-200"
          >
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
            </svg>
          </button>
        </div>
      )}
    </div>
  )
}
