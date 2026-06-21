import { useState, useEffect } from 'react'
import { API_BASE } from '../lib/api'

export interface ProfileSummary {
  profile_id: string
  created_at: string | number | null
  mutation_count: number
}

export function useProfileHistory() {
  const [profiles, setProfiles] = useState<ProfileSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    fetch(`${API_BASE}/api/profiles`)
      .then((r) => {
        if (!r.ok) throw new Error(`${r.status} ${r.statusText}`)
        return r.json() as Promise<ProfileSummary[]>
      })
      .then((data) => {
        if (!cancelled) {
          setProfiles(data)
          setLoading(false)
        }
      })
      .catch((e: unknown) => {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : String(e))
          setLoading(false)
        }
      })
    return () => { cancelled = true }
  }, [])

  return { profiles, loading, error }
}
