import { useState, useCallback } from 'react'
import type { HydratedMutation } from '../types'

export interface ChatMessage {
  id: string
  role: 'user' | 'agent'
  content: string
  streaming?: boolean
}

function uid() {
  return Math.random().toString(36).slice(2)
}

function sleep(ms: number) {
  return new Promise((r) => setTimeout(r, ms))
}

export function useChat(getMutations: () => HydratedMutation[]) {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [busy, setBusy] = useState(false)

  const send = useCallback(async (text: string) => {
    if (!text.trim() || busy) return

    const userMsg: ChatMessage = { id: uid(), role: 'user', content: text.trim() }
    const agentId = uid()
    const agentMsg: ChatMessage = { id: agentId, role: 'agent', content: '', streaming: true }

    setMessages((prev) => [...prev, userMsg, agentMsg])
    setBusy(true)

    let responseText = ''

    try {
      const mutations = getMutations()
      const resp = await fetch('/api/query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          question: text.trim(),
          context: mutations.map((m) => ({
            mutation_id: m.mutation_id,
            protein: m.protein,
            estimated_effect: m.estimated_effect,
            justification: m.justification,
          })),
        }),
      })

      if (resp.ok) {
        const data = await resp.json() as Record<string, unknown>
        // Backend returns { report, verdict, subgraph, rows, cited_pathways }
        responseText = String(data['report'] ?? data['message'] ?? JSON.stringify(data))
      } else {
        responseText = `Error ${resp.status}: the query endpoint returned an error.`
      }
    } catch {
      responseText = 'Could not reach the backend. Make sure the server is running on port 8000.'
    }

    // Stream the response text in word by word for readability
    const words = responseText.split(' ')
    let accumulated = ''
    for (const word of words) {
      accumulated += (accumulated ? ' ' : '') + word
      const snap = accumulated
      setMessages((prev) =>
        prev.map((m) => (m.id === agentId ? { ...m, content: snap } : m)),
      )
      await sleep(15)
    }

    setMessages((prev) =>
      prev.map((m) => (m.id === agentId ? { ...m, streaming: false } : m)),
    )
    setBusy(false)
  }, [busy, getMutations])

  const clear = useCallback(() => setMessages([]), [])

  return { messages, busy, send, clear }
}
