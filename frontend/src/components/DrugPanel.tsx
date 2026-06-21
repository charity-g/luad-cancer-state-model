import type { DrugHit } from '../types'

const STATUS_COLOR: Record<string, string> = {
  FDA_APPROVED:          'bg-emerald-900/60 text-emerald-300 border-emerald-700',
  APPROVED:              'bg-emerald-900/60 text-emerald-300 border-emerald-700',
  INVESTIGATIONAL:       'bg-amber-900/60  text-amber-300  border-amber-700',
  CLINICAL_TRIAL:        'bg-amber-900/60  text-amber-300  border-amber-700',
  PRECLINICAL:           'bg-slate-800     text-slate-400  border-slate-600',
}

function statusBadge(status: string) {
  const cls = STATUS_COLOR[status.toUpperCase()] ?? 'bg-slate-800 text-slate-400 border-slate-600'
  const label = status.replace(/_/g, ' ')
  return (
    <span className={`rounded border px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${cls}`}>
      {label}
    </span>
  )
}

interface Props {
  drugs: DrugHit[]
}

export default function DrugPanel({ drugs }: Props) {
  if (!drugs.length) {
    return (
      <div className="flex flex-1 items-center justify-center text-sm text-slate-500">
        No drug data available for this session yet.
      </div>
    )
  }

  // Group by target protein, deduplicate by drugbank_id within each group.
  const byGene: Record<string, DrugHit[]> = {}
  const seen = new Set<string>()
  for (const d of drugs) {
    const key = d.drugbank_id || d.drug_name
    if (seen.has(key)) continue
    seen.add(key)
    const g = d.gene_symbol || 'Unknown target'
    ;(byGene[g] ??= []).push(d)
  }

  return (
    <div className="flex flex-1 flex-col overflow-y-auto p-4 gap-6">
      {/* Header */}
      <div>
        <h2 className="text-sm font-semibold text-slate-200">Drug Targets</h2>
        <p className="mt-0.5 text-xs text-slate-500">
          {drugs.length} drug{drugs.length !== 1 ? 's' : ''} identified via Therapeutic Target Database
        </p>
      </div>

      {/* Groups */}
      {Object.entries(byGene).map(([gene, geneDrugs]) => (
        <section key={gene}>
          {/* Gene header */}
          <div className="mb-2 flex items-center gap-2">
            <span className="h-px flex-1 bg-slate-700" />
            <span className="rounded bg-slate-800 px-2 py-0.5 font-mono text-xs font-semibold text-blue-300">
              {gene}
            </span>
            <span className="h-px flex-1 bg-slate-700" />
          </div>

          {/* Drug cards */}
          <div className="flex flex-col gap-2">
            {geneDrugs.map((d) => (
              <div
                key={d.drugbank_id || d.drug_name}
                className="rounded-lg border border-slate-700 bg-slate-800/60 p-3"
              >
                <div className="flex items-start justify-between gap-2">
                  <span className="text-sm font-medium text-slate-100">{d.drug_name}</span>
                  {d.approval_status && statusBadge(d.approval_status)}
                </div>

                {d.mechanism && (
                  <p className="mt-1.5 text-xs leading-relaxed text-slate-400">{d.mechanism}</p>
                )}

                {d.drugbank_id && (
                  <p className="mt-2 font-mono text-[10px] text-slate-600">
                    DrugBank: {d.drugbank_id}
                  </p>
                )}
              </div>
            ))}
          </div>
        </section>
      ))}
    </div>
  )
}
