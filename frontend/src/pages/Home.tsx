import { Link, useNavigate } from 'react-router-dom'
import { useProfileHistory } from '../hooks/useProfileHistory'

function formatDate(value: string | number | null) {
  if (value == null) return 'Unknown date'
  try {
    // Neo4j timestamp() returns milliseconds as a number; ISO strings also accepted
    const d = typeof value === 'number' ? new Date(value) : new Date(value)
    if (isNaN(d.getTime())) return String(value)
    return d.toLocaleString(undefined, {
      month: 'short', day: 'numeric', year: 'numeric',
      hour: '2-digit', minute: '2-digit',
    })
  } catch {
    return String(value)
  }
}

export default function Home() {
  const navigate = useNavigate()
  const { profiles, loading, error } = useProfileHistory()

  function loadProfile(profileId: string) {
    navigate(`/model?profileId=${profileId}`)
  }

  return (
    <div className="space-y-8">
      {/* Hero */}
      <div>
        <h1 className="text-3xl font-bold tracking-tight text-slate-900">
          Cancer State Modelling
        </h1>
        <p className="mt-2 max-w-2xl text-slate-700 text-sm">
          Upload a mutation profile CSV to identify variants, annotate protein effects, and
          visualize affected KEGG pathways.
        </p>
        <Link
          to="/model"
          className="mt-5 inline-flex items-center gap-2 rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700 transition-colors"
        >
          <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
          New analysis
        </Link>
      </div>

      {/* History */}
      <div>
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-700 mb-3">
          Previous profiles
        </h2>

        {loading && (
          <div className="flex items-center gap-2 text-sm text-slate-400">
            <svg className="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
            </svg>
            Loading history…
          </div>
        )}

        {error && (
          <p className="text-sm text-red-500">
            Could not load history: {error}
          </p>
        )}

        {!loading && !error && profiles.length === 0 && (
          <p className="text-sm text-slate-400">
            No profiles yet. Upload a mutation CSV to get started.
          </p>
        )}

        {!loading && profiles.length > 0 && (
          <ul className="space-y-2">
            {profiles.map((p) => (
              <li
                key={p.profile_id}
                className="flex items-center justify-between rounded-lg border border-slate-200 bg-white px-4 py-3 shadow-sm hover:border-slate-300 transition-colors"
              >
                <div className="min-w-0">
                  <p className="text-sm font-mono font-medium text-slate-800 truncate">
                    {p.profile_id}
                  </p>
                  <p className="mt-0.5 text-xs text-slate-400">
                    {formatDate(p.created_at as string | number | null)}
                    {p.mutation_count > 0 && (
                      <span className="ml-2 inline-flex items-center rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-600">
                        {p.mutation_count} mutation{p.mutation_count !== 1 ? 's' : ''}
                      </span>
                    )}
                  </p>
                </div>
                <button
                  onClick={() => loadProfile(p.profile_id)}
                  className="ml-4 flex-shrink-0 rounded-md border border-slate-200 px-3 py-1.5 text-xs font-medium text-slate-600 hover:border-slate-400 hover:text-slate-900 transition-colors"
                >
                  Load →
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}
