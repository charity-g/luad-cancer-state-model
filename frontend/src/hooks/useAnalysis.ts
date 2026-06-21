import { useState, useCallback } from 'react'
import type { MutationEntry, HydratedMutation } from '../types'
import { API_BASE } from '../lib/api'

export type AnalysisPhase = 'idle' | 'streaming' | 'done' | 'error'

export function useAnalysis() {
  const [mutations, setMutations] = useState<MutationEntry[]>([])
  const [phase, setPhase] = useState<AnalysisPhase>('idle')
  const [error, setError] = useState<string | null>(null)
  const [profileId, setProfileId] = useState<string | null>(null)

  const analyze = useCallback(async (file: File) => {
    setMutations([])
    setPhase('streaming')
    setError(null)
    setProfileId(null)

    const body = new FormData()
    body.append('file', file)

    let resp: Response
    try {
      resp = await fetch(`${API_BASE}/api/profiles/stream`, { method: 'POST', body })
    } catch {
      setError('Cannot connect to the backend. Is the server running on port 8000?')
      setPhase('error')
      return
    }

    if (!resp.ok) {
      let detail = `${resp.status} ${resp.statusText}`
      try {
        const errBody = (await resp.json()) as Record<string, unknown>
        detail = String(errBody['detail'] ?? errBody['message'] ?? detail)
      } catch { /* ignore parse failure, use status text */ }
      setError(`Upload failed: ${detail}`)
      setPhase('error')
      return
    }

    if (!resp.body) {
      setError('Server returned an empty response body.')
      setPhase('error')
      return
    }

    const reader = resp.body.getReader()
    const decoder = new TextDecoder()
    let buf = ''

    try {
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buf += decoder.decode(value, { stream: true })

        const frames = buf.split('\n\n')
        buf = frames.pop() ?? ''

        for (const frame of frames) {
          const eventLine = frame.split('\n').find((l) => l.startsWith('event:'))
          const dataLine  = frame.split('\n').find((l) => l.startsWith('data:'))
          if (!eventLine || !dataLine) continue

          const event = eventLine.replace('event:', '').trim()
          let payload: Record<string, unknown>
          try {
            payload = JSON.parse(dataLine.replace('data:', '').trim()) as Record<string, unknown>
          } catch {
            continue // skip malformed frames
          }

          if (event === 'started') {
            const pid = payload['profile_id']
            if (typeof pid === 'string') setProfileId(pid)
          }

          if (event === 'mutations_extracted') {
            const raw = payload['mutations'] as Record<string, unknown>[] | undefined
            if (Array.isArray(raw)) {
              setMutations(
                raw.map((m, i) => ({
                  mutation_id: String(m['mutation_id'] ?? ''),
                  // Mark the first one as hydrating immediately so the sidebar shows activity
                  status: i === 0 ? ('hydrating' as const) : ('identified' as const),
                }))
              )
            }
          }

          if (event === 'error') {
            const mutationPayload = payload['mutation'] as Record<string, unknown> | undefined
            const message = String(payload['message'] ?? 'An error occurred during analysis.')
            if (mutationPayload) {
              // Per-mutation error — stream continues, mark just this mutation failed
              const mutation_id = String(mutationPayload['mutation_id'] ?? '')
              setMutations((prev) => {
                const exists = prev.find((m) => m.mutation_id === mutation_id)
                if (exists) {
                  return prev.map((m) =>
                    m.mutation_id === mutation_id ? { ...m, status: 'failed', error: message } : m,
                  )
                }
                return [...prev, { mutation_id, status: 'failed', error: message }]
              })
            } else {
              // Fatal stream error
              setError(message)
              setPhase('error')
              return
            }
          }

          if (event === 'mutation_hydrated') {
            const raw      = payload['mutation'] as Record<string, unknown>
            const hydrated = payload['hydrated'] as Record<string, unknown>
            const mutation_id = String(raw['mutation_id'] ?? '')

            // Raw DepMap CSV columns survive under mutation.raw; use them for
            // drug routing since the LLM hydration can drop gene/variant/flags.
            const rawCsv = ((raw['raw'] as Record<string, unknown>) ?? {})
            const csvStr = (k: string) => {
              const v = rawCsv[k]
              return v === undefined || v === null || v === '' ? undefined : String(v)
            }
            const csvBool = (k: string) => String(rawCsv[k] ?? '').toUpperCase() === 'TRUE'

            const identifiers = (hydrated['identifiers'] as Record<string, unknown>) ?? {}
            const hgvs = csvStr('ProteinChange') ?? (identifiers['hgvs_protein'] ? String(identifiers['hgvs_protein']) : undefined)
            const hydratedMutation: HydratedMutation = {
              mutation_id,
              protein:          String(hydrated['protein'] ?? ''),
              identifiers:      (hydrated['identifiers'] as Record<string, unknown>) ?? {},
              estimated_effect: (hydrated['estimated_effect'] as HydratedMutation['estimated_effect']) ?? 'no_effect',
              confidence:       String(hydrated['confidence'] ?? ''),
              justification:    (hydrated['justification'] as Record<string, unknown>) ?? {},
              hgvs_protein:     hgvs,
              gene:             csvStr('HugoSymbol'),
              features: {
                is_hotspot:           csvBool('Hotspot'),
                is_lof:               csvBool('LikelyLoF') || csvBool('TranscriptLikelyLof'),
                is_high_impact:       (csvStr('VepImpact') ?? '').toUpperCase() === 'HIGH',
                oncogene_high_impact: csvBool('OncogeneHighImpact'),
                tsg_high_impact:      csvBool('TumorSuppressorHighImpact'),
              },
            }

            setMutations((prev) => {
              const updated = prev.map((m) =>
                m.mutation_id === mutation_id
                  ? { ...m, status: 'done' as const, hydrated: hydratedMutation }
                  : m
              )
              // If the mutation wasn't in the bulk list, append it
              if (!prev.find((m) => m.mutation_id === mutation_id)) {
                updated.push({ mutation_id, status: 'done', hydrated: hydratedMutation })
              }
              // Mark the next identified mutation as hydrating so the sidebar shows a spinner
              const nextIdx = updated.findIndex((m) => m.status === 'identified')
              if (nextIdx !== -1) updated[nextIdx] = { ...updated[nextIdx], status: 'hydrating' }
              return updated
            })
          }

          if (event === 'complete') {
            setPhase('done')
          }
        }
      }
    } catch (streamErr) {
      const msg = streamErr instanceof Error ? streamErr.message : String(streamErr)
      setError(`Stream interrupted: ${msg}`)
      setPhase('error')
      return
    }

    setPhase('done')
  }, [])

  const patchMutation = useCallback((mutation_id: string, patch: Partial<MutationEntry>) => {
    setMutations((prev) =>
      prev.map((m) => (m.mutation_id === mutation_id ? { ...m, ...patch } : m))
    )
  }, [])

  const reset = useCallback(() => {
    setMutations([])
    setPhase('idle')
    setError(null)
    setProfileId(null)
  }, [])

  return { mutations, phase, error, profileId, analyze, reset, patchMutation }
}
