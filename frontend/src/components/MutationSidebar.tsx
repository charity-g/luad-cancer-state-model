import type { MutationEntry, EffectType } from '../types'

const effectColors: Record<EffectType, string> = {
  activating:        'bg-amber-100 text-amber-800 border-amber-200',
  gain_of_function:  'bg-amber-100 text-amber-800 border-amber-200',
  inactivating:      'bg-red-100 text-red-800 border-red-200',
  loss_of_function:  'bg-red-100 text-red-800 border-red-200',
  uncertain:         'bg-purple-100 text-purple-700 border-purple-200',
  no_effect:         'bg-slate-100 text-slate-600 border-slate-200',
}

const effectShort: Record<EffectType, string> = {
  activating:       'ACT',
  gain_of_function: 'GOF',
  inactivating:     'INACT',
  loss_of_function: 'LOF',
  uncertain:        'UNC',
  no_effect:        'NONE',
}

interface Props {
  mutations: MutationEntry[]
  selected: string | null
  onSelect: (id: string) => void
  phase: 'idle' | 'streaming' | 'done' | 'error'
  filename: string
  onReset: () => void
}

export default function MutationSidebar({ mutations, selected, onSelect, phase, filename, onReset }: Props) {
  const done = mutations.filter((m) => m.status === 'done').length

  return (
    <aside className="flex h-full w-64 flex-shrink-0 flex-col border-r border-slate-200 bg-white">
      <div className="border-b border-slate-100 px-4 py-3">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <p className="truncate text-sm font-medium text-slate-800">{filename}</p>
            <p className="mt-0.5 text-xs text-slate-400">
              {mutations.length} variant{mutations.length !== 1 ? 's' : ''}
              {phase === 'streaming' && ' · analyzing…'}
              {phase === 'done' && ` · ${done} annotated`}
              {phase === 'error' && <span className="text-red-500"> · failed</span>}
            </p>
          </div>
          <button
            onClick={onReset}
            className="flex-shrink-0 rounded p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600"
            title="Upload new file"
          >
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
            </svg>
          </button>
        </div>

        {phase === 'streaming' && mutations.length > 0 && (
          <div className="mt-2 h-1 w-full overflow-hidden rounded-full bg-slate-100">
            <div
              className="h-full rounded-full bg-blue-500 transition-all duration-300"
              style={{ width: `${(done / mutations.length) * 100}%` }}
            />
          </div>
        )}
      </div>

      <ul className="flex-1 divide-y divide-slate-100 overflow-y-auto">
        {mutations.length === 0 && phase === 'streaming' && (
          <li className="flex flex-col items-center justify-center py-10 text-slate-400">
            <div className="h-4 w-4 animate-spin rounded-full border-2 border-slate-200 border-t-blue-500" />
            <p className="mt-2 text-xs">Identifying variants…</p>
          </li>
        )}

        {mutations.map((m) => (
          <li key={m.mutation_id}>
            <button
              onClick={() => onSelect(m.mutation_id)}
              className={`w-full px-4 py-2.5 text-left transition-colors hover:bg-slate-50 ${
                selected === m.mutation_id ? 'border-l-2 border-blue-500 bg-blue-50' : ''
              }`}
            >
              <div className="flex items-center justify-between gap-2">
                <span className="min-w-0 truncate font-mono text-xs font-medium text-slate-700">
                  {m.mutation_id}
                </span>

                {m.status === 'identified' && (
                  <span className="h-1.5 w-1.5 flex-shrink-0 rounded-full bg-slate-300" />
                )}
                {m.status === 'hydrating' && (
                  <span className="h-3.5 w-3.5 flex-shrink-0 animate-spin rounded-full border-2 border-slate-200 border-t-blue-500" />
                )}
                {m.status === 'done' && m.hydrated && (
                  <span className={`flex-shrink-0 rounded border px-1.5 py-0.5 text-[10px] font-semibold ${effectColors[m.hydrated.estimated_effect as EffectType]}`}>
                    {effectShort[m.hydrated.estimated_effect as EffectType]}
                  </span>
                )}
                {m.status === 'failed' && (
                  <span className="flex-shrink-0 rounded border border-red-200 bg-red-50 px-1.5 py-0.5 text-[10px] font-semibold text-red-500">
                    ERR
                  </span>
                )}
              </div>

              {m.status === 'done' && m.hydrated && (
                <p className="mt-0.5 text-[11px] text-slate-400">{m.hydrated.protein}</p>
              )}
              {m.status === 'failed' && m.error && (
                <p className="mt-0.5 line-clamp-2 text-[11px] text-red-400">{m.error}</p>
              )}
            </button>
          </li>
        ))}
      </ul>
    </aside>
  )
}
