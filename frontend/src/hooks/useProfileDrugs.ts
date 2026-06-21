import { useState, useEffect } from 'react'
import type { DrugHit } from '../types'

export interface ProfileDrug extends DrugHit {
  estimated_effect?: string
  mutation_id?: string
}

export function useProfileDrugs(profileId: string | null) {
  const [drugs, setDrugs] = useState<ProfileDrug[]>([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!profileId) { setDrugs([]); return }

    let cancelled = false
    setLoading(true)

    fetch(`/api/profiles/${profileId}/drugs`)
      .then((r) => (r.ok ? r.json() as Promise<ProfileDrug[]> : Promise.resolve([])))
      .then((data) => { if (!cancelled) { setDrugs(data); setLoading(false) } })
      .catch(() => { if (!cancelled) { setDrugs([]); setLoading(false) } })

    return () => { cancelled = true }
  }, [profileId])

  return { drugs, loading }
}
