import { useState, useEffect } from 'react'

export interface DomainRange {
  name: string
  uniprot_start: number
  uniprot_end: number
  pdb_start: number | null
  pdb_end: number | null
}

export interface ProteinDomainsResult {
  uniprot_ac: string
  pdb_id: string | null
  chain: string | null
  domains: DomainRange[]
  sifts_available: boolean
}

interface State {
  data: ProteinDomainsResult | null
  loading: boolean
  error: string | null
}

const cache = new Map<string, ProteinDomainsResult>()

export function useProteinDomains(uniprotAc: string | null) {
  const [state, setState] = useState<State>({ data: null, loading: false, error: null })

  useEffect(() => {
    if (!uniprotAc) {
      setState({ data: null, loading: false, error: null })
      return
    }

    const ac = uniprotAc.toUpperCase()

    if (cache.has(ac)) {
      setState({ data: cache.get(ac)!, loading: false, error: null })
      return
    }

    let cancelled = false
    setState({ data: null, loading: true, error: null })

    fetch(`/api/proteins/${ac}/domains`)
      .then(async (resp) => {
        if (!resp.ok) {
          const body = await resp.json().catch(() => ({})) as Record<string, unknown>
          throw new Error(String(body['detail'] ?? `${resp.status} ${resp.statusText}`))
        }
        return resp.json() as Promise<ProteinDomainsResult>
      })
      .then((data) => {
        if (cancelled) return
        cache.set(ac, data)
        setState({ data, loading: false, error: null })
      })
      .catch((err: unknown) => {
        if (cancelled) return
        setState({ data: null, loading: false, error: err instanceof Error ? err.message : String(err) })
      })

    return () => { cancelled = true }
  }, [uniprotAc])

  return state
}
