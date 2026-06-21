import { useState, useCallback } from 'react'
import type { HydratedMutation, ContextCard } from '../types'

export interface ChatMessage {
  id: string
  role: 'user' | 'agent'
  content: string
  streaming?: boolean
  context: ContextCard[]
  thread: string // protein name or 'General'
  followUps?: string[]
}

function uid() {
  return Math.random().toString(36).slice(2)
}

function sleep(ms: number) {
  return new Promise((r) => setTimeout(r, ms))
}

function deriveThread(context: ContextCard[]): string {
  if (context.length === 1) return context[0].protein
  if (context.length > 1) return context.map((c) => c.protein).join(' / ')
  return 'General'
}

function deriveFollowUps(context: ContextCard[]): string[] {
  if (context.length === 0) return []
  const p = context[0]
  return [
    `What drugs target ${p.protein}?`,
    `Which downstream proteins are affected by ${p.protein}?`,
    `How does ${p.effect.replace('_', ' ')} ${p.protein} affect cell proliferation?`,
  ]
}

export function useChat(getMutations: () => HydratedMutation[]) {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [busy, setBusy] = useState(false)

  const send = useCallback(
    async (text: string, context: ContextCard[]) => {
      if (!text.trim() || busy) return

      const thread = deriveThread(context)
      const userMsg: ChatMessage = { id: uid(), role: 'user', content: text.trim(), context, thread }
      const agentId = uid()
      const agentMsg: ChatMessage = {
        id: agentId,
        role: 'agent',
        content: '',
        streaming: true,
        context,
        thread,
      }

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
            context: context.map((c) => ({ ...c })),
            mutations: mutations.map((m) => ({
              mutation_id: m.mutation_id,
              protein: m.protein,
              estimated_effect: m.estimated_effect,
              justification: m.justification,
            })),
          }),
        })

        if (resp.ok) {
          const data = (await resp.json()) as Record<string, unknown>
          responseText = String(data['report'] ?? data['message'] ?? JSON.stringify(data))
        } else {
          responseText = `Error ${resp.status}: the query endpoint returned an error.`
        }
      } catch {
        responseText =
          'Could not reach the backend. Make sure the server is running on port 8000.'
      }

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

      const followUps = deriveFollowUps(context)
      setMessages((prev) =>
        prev.map((m) =>
          m.id === agentId ? { ...m, streaming: false, followUps } : m,
        ),
      )
      setBusy(false)
    },
    [busy, getMutations],
  )

  const clear = useCallback(() => setMessages([]), [])

  return { messages, busy, send, clear }
}
