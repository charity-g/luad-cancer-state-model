import { MutationEntry } from '../types'

interface Props {
  entry: MutationEntry | undefined
}

const effectConfig = {
  activating: {
    label: 'Activating',
    bg: 'bg-amber-50',
    border: 'border-amber-200',
    badge: 'bg-amber-100 text-amber-800',
    dot: 'bg-amber-400',
    description: 'Gain-of-function variant predicted to increase protein activity or signaling output.',
  },
  inactivating: {
    label: 'Inactivating',
    bg: 'bg-red-50',
    border: 'border-red-200',
    badge: 'bg-red-100 text-red-800',
    dot: 'bg-red-400',
    description: 'Loss-of-function variant predicted to reduce or abolish normal protein activity.',
  },
  no_effect: {
    label: 'No Effect',
    bg: 'bg-slate-50',
    border: 'border-slate-200',
    badge: 'bg-slate-100 text-slate-600',
    dot: 'bg-slate-400',
    description: 'Variant predicted to have minimal impact on protein function.',
  },
}

export default function MutationDetail({ entry }: Props) {
  if (!entry) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center text-slate-400">
        <svg className="mb-3 h-8 w-8" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
            d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
          />
        </svg>
        <p className="text-sm">Select a mutation to view details</p>
      </div>
    )
  }

  if (entry.status === 'identified') {
    return (
      <div className="flex flex-1 flex-col items-center justify-center text-slate-400">
        <p className="font-mono text-sm font-medium text-slate-600">{entry.mutation_id}</p>
        <p className="mt-1 text-xs">Queued for annotation…</p>
      </div>
    )
  }

  if (entry.status === 'hydrating') {
    return (
      <div className="flex flex-1 flex-col items-center justify-center text-slate-400">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-slate-200 border-t-blue-500" />
        <p className="mt-3 font-mono text-sm font-medium text-slate-600">{entry.mutation_id}</p>
        <p className="mt-1 text-xs">Annotating variant…</p>
      </div>
    )
  }

  const h = entry.hydrated!
  const cfg = effectConfig[h.estimated_effect]

  return (
    <div className="flex flex-1 flex-col overflow-y-auto px-6 py-6">
      <div className="mb-1 font-mono text-xs text-slate-400">mutation</div>
      <h2 className="font-mono text-lg font-bold text-slate-800">{h.mutation_id}</h2>

      <div className={`mt-5 rounded-xl border p-4 ${cfg.bg} ${cfg.border}`}>
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-full bg-white shadow-sm">
            <span className="text-sm font-bold text-slate-700">{h.protein}</span>
          </div>
          <div>
            <p className="text-xs text-slate-500">Target protein</p>
            <p className="font-semibold text-slate-800">{h.protein}</p>
          </div>
          <div className="ml-auto">
            <span className={`flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-semibold ${cfg.badge}`}>
              <span className={`h-1.5 w-1.5 rounded-full ${cfg.dot}`} />
              {cfg.label}
            </span>
          </div>
        </div>
        <p className="mt-3 text-xs text-slate-600">{cfg.description}</p>
      </div>

      <div className="mt-5">
        <h3 className="mb-3 text-xs font-semibold uppercase tracking-widest text-slate-400">
          Justification
        </h3>
        <div className="divide-y divide-slate-100 rounded-lg border border-slate-200 bg-white">
          {Object.entries(h.justification).map(([key, val]) => (
            <div key={key} className="flex items-start gap-3 px-4 py-2.5">
              <span className="mt-0.5 min-w-[140px] font-mono text-[11px] text-slate-400">
                {key.replace(/_/g, ' ')}
              </span>
              <span className="text-xs text-slate-700">{String(val)}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
