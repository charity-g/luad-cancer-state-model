import type { MutationEntry, EffectType } from '../types'

const effectConfig: Record<EffectType, {
  label: string; bg: string; border: string; badge: string; dot: string; description: string
}> = {
  activating: {
    label: 'Activating',
    bg: 'bg-amber-50', border: 'border-amber-200',
    badge: 'bg-amber-100 text-amber-800', dot: 'bg-amber-400',
    description: 'Variant predicted to increase protein activity or signaling output.',
  },
  gain_of_function: {
    label: 'Gain of Function',
    bg: 'bg-amber-50', border: 'border-amber-200',
    badge: 'bg-amber-100 text-amber-800', dot: 'bg-amber-500',
    description: 'Variant confers a new or enhanced activity not present in the wild-type protein.',
  },
  inactivating: {
    label: 'Inactivating',
    bg: 'bg-red-50', border: 'border-red-200',
    badge: 'bg-red-100 text-red-800', dot: 'bg-red-400',
    description: 'Variant predicted to reduce or abolish normal protein activity.',
  },
  loss_of_function: {
    label: 'Loss of Function',
    bg: 'bg-red-50', border: 'border-red-200',
    badge: 'bg-red-100 text-red-800', dot: 'bg-red-500',
    description: 'Variant disrupts normal protein function, eliminating or severely reducing activity.',
  },
  uncertain: {
    label: 'Uncertain',
    bg: 'bg-purple-50', border: 'border-purple-200',
    badge: 'bg-purple-100 text-purple-700', dot: 'bg-purple-400',
    description: 'Functional consequence of this variant cannot be confidently determined.',
  },
  no_effect: {
    label: 'No Effect',
    bg: 'bg-slate-50', border: 'border-slate-200',
    badge: 'bg-slate-100 text-slate-600', dot: 'bg-slate-400',
    description: 'Variant predicted to have minimal impact on protein function.',
  },
}

const confidenceColors: Record<string, string> = {
  high:   'bg-emerald-100 text-emerald-700',
  medium: 'bg-amber-100 text-amber-700',
  low:    'bg-red-100 text-red-600',
}

interface Props {
  entry: MutationEntry | undefined
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

  if (entry.status === 'failed') {
    return (
      <div className="flex flex-1 flex-col overflow-y-auto px-6 py-6">
        <div className="mb-1 font-mono text-xs text-slate-400">mutation</div>
        <h2 className="font-mono text-lg font-bold text-slate-800">{entry.mutation_id}</h2>
        <div className="mt-5 rounded-xl border border-red-200 bg-red-50 p-4">
          <div className="flex items-start gap-3">
            <svg className="mt-0.5 h-4 w-4 flex-shrink-0 text-red-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M12 9v2m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
            </svg>
            <div>
              <p className="text-xs font-semibold text-red-700">Annotation failed</p>
              {entry.error && <p className="mt-1 text-xs leading-relaxed text-red-600">{entry.error}</p>}
            </div>
          </div>
        </div>
      </div>
    )
  }

  const h = entry.hydrated!
  const effect = h.estimated_effect as EffectType
  const cfg = effectConfig[effect] ?? effectConfig.no_effect
  const confidenceCls = confidenceColors[h.confidence?.toLowerCase()] ?? 'bg-slate-100 text-slate-600'

  return (
    <div className="flex flex-1 flex-col overflow-y-auto px-6 py-6">
      <div className="mb-1 font-mono text-xs text-slate-400">mutation</div>
      <h2 className="font-mono text-lg font-bold text-slate-800">{h.mutation_id}</h2>

      {/* protein + effect card */}
      <div className={`mt-5 rounded-xl border p-4 ${cfg.bg} ${cfg.border}`}>
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-full bg-white shadow-sm">
            <span className="text-xs font-bold text-slate-700">{h.protein.slice(0, 4)}</span>
          </div>
          <div className="min-w-0">
            <p className="text-xs text-slate-500">Target protein</p>
            <p className="font-semibold text-slate-800">{h.protein}</p>
          </div>
          <div className="ml-auto flex flex-col items-end gap-1.5">
            <span className={`flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-semibold ${cfg.badge}`}>
              <span className={`h-1.5 w-1.5 rounded-full ${cfg.dot}`} />
              {cfg.label}
            </span>
            {h.confidence && (
              <span className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${confidenceCls}`}>
                {h.confidence} confidence
              </span>
            )}
          </div>
        </div>
        <p className="mt-3 text-xs text-slate-600">{cfg.description}</p>
      </div>

      {/* identifiers */}
      {Object.keys(h.identifiers).length > 0 && (
        <div className="mt-5">
          <h3 className="mb-3 text-xs font-semibold uppercase tracking-widest text-slate-400">
            Identifiers
          </h3>
          <div className="divide-y divide-slate-100 rounded-lg border border-slate-200 bg-white">
            {Object.entries(h.identifiers).map(([key, val]) => (
              <div key={key} className="flex items-start gap-3 px-4 py-2">
                <span className="mt-0.5 min-w-[120px] font-mono text-[11px] text-slate-400">
                  {key.replace(/_/g, ' ')}
                </span>
                <span className="text-xs text-slate-700">{String(val)}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* justification */}
      {Object.keys(h.justification).length > 0 && (
        <div className="mt-5">
          <h3 className="mb-3 text-xs font-semibold uppercase tracking-widest text-slate-400">
            Justification
          </h3>
          <div className="divide-y divide-slate-100 rounded-lg border border-slate-200 bg-white">
            {Object.entries(h.justification).map(([key, val]) => (
              <div key={key} className="flex items-start gap-3 px-4 py-2.5">
                <span className="mt-0.5 min-w-[120px] font-mono text-[11px] text-slate-400">
                  {key.replace(/_/g, ' ')}
                </span>
                <span className="text-xs leading-relaxed text-slate-700">{String(val)}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
