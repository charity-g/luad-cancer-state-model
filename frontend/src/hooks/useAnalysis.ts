import { useState, useCallback } from 'react'
import type { MutationEntry, HydratedMutation } from '../types'

export function useAnalysis() {
  const [mutations, setMutations] = useState<MutationEntry[]>([])
  const [phase, setPhase] = useState<'idle' | 'streaming' | 'done'>('idle')

  const analyze = useCallback(async (file: File) => {
    setMutations([])
    setPhase('streaming')

    const body = new FormData()
    body.append('file', file)

    let resp: Response
    try {
      resp = await fetch('/api/profiles/stream', { method: 'POST', body })
    } catch {
      setPhase('done')
      return
    }

    if (!resp.ok || !resp.body) {
      setPhase('done')
      return
    }

    const reader = resp.body.getReader()
    const decoder = new TextDecoder()
    let buf = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buf += decoder.decode(value, { stream: true })

      // Parse SSE frames from buffer
      const frames = buf.split('\n\n')
      buf = frames.pop() ?? ''

      for (const frame of frames) {
        const eventLine = frame.split('\n').find((l) => l.startsWith('event:'))
        const dataLine  = frame.split('\n').find((l) => l.startsWith('data:'))
        if (!eventLine || !dataLine) continue

        const event = eventLine.replace('event:', '').trim()
        let payload: Record<string, unknown>
        try {
          payload = JSON.parse(dataLine.replace('data:', '').trim())
        } catch {
          continue
        }

        if (event === 'mutations_extracted') {
          // Backend gives us the count but not the IDs yet — wait for hydration events
        }

        if (event === 'mutation_hydrated') {
          const raw      = payload['mutation'] as Record<string, unknown>
          const hydrated = payload['hydrated'] as Record<string, unknown>
          const mutation_id = String(raw['mutation_id'] ?? '')

          const hydratedMutation: HydratedMutation = {
            mutation_id,
            protein:          String(hydrated['protein'] ?? ''),
            estimated_effect: (hydrated['estimated_effect'] as HydratedMutation['estimated_effect']) ?? 'no_effect',
            justification:    (hydrated['justification'] as Record<string, unknown>) ?? {},
          }

          setMutations((prev) => {
            const exists = prev.find((m) => m.mutation_id === mutation_id)
            if (exists) {
              return prev.map((m) =>
                m.mutation_id === mutation_id ? { ...m, status: 'done', hydrated: hydratedMutation } : m,
              )
            }
            return [...prev, { mutation_id, status: 'done', hydrated: hydratedMutation }]
          })
        }

        if (event === 'complete') {
          setPhase('done')
        }
      }
    }

    setPhase('done')
  }, [])

  const reset = useCallback(() => {
    setMutations([])
    setPhase('idle')
  }, [])

  return { mutations, phase, analyze, reset }
}
