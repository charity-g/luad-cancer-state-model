import { useState, useEffect } from 'react'
import type { ProfileGraph } from './useProfileGraph'

export function useProfilePPI(profileId: string | null) {
  const [graph, setGraph]     = useState<ProfileGraph | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError]     = useState<string | null>(null)

  useEffect(() => {
    if (!profileId) { setGraph(null); return }

    let cancelled = false
    setLoading(true)
    setError(null)

    // Use the cascade endpoint: traverses outward from seed proteins through
    // signaling edges and tags outcome genes (growth / proliferation / apoptosis)
    fetch(`/api/profiles/${profileId}/ppi/cascade`)
      .then((r) => {
        if (r.status === 404) return null
        if (!r.ok) throw new Error(`${r.status} ${r.statusText}`)
        return r.json() as Promise<ProfileGraph>
      })
      .then((data) => { if (!cancelled) { setGraph(data); setLoading(false) } })
      .catch((e: unknown) => {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : String(e))
          setLoading(false)
        }
      })

    return () => { cancelled = true }
  }, [profileId])

  return { graph, loading, error }
}
