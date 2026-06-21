import { useState, useCallback } from 'react'
import type { HydratedMutation, ContextCard } from '../types'

export interface ChatMessage {
  id: string
  role: 'user' | 'agent'
  content: string
  streaming?: boolean
  isError?: boolean
  context: ContextCard[]
  thread: string
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

function errorMessage(agentId: string, text: string, context: ContextCard[], thread: string): ChatMessage {
  return { id: agentId, role: 'agent', content: text, isError: true, context, thread }
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
      const agentMsg: ChatMessage = { id: agentId, role: 'agent', content: '', streaming: true, context, thread }

      setMessages((prev) => [...prev, userMsg, agentMsg])
      setBusy(true)

      let responseText = ''
      let isError = false

      try {
        const mutations = getMutations()
        let resp: Response
        try {
          resp = await fetch('/api/query', {
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
        } catch {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === agentId
                ? errorMessage(agentId, 'Cannot reach the backend — is the server running on port 8000?', context, thread)
                : m,
            ),
          )
          setBusy(false)
          return
        }

        if (!resp.ok) {
          let detail = `${resp.status} ${resp.statusText}`
          try {
            const errBody = (await resp.json()) as Record<string, unknown>
            detail = String(errBody['detail'] ?? errBody['message'] ?? detail)
          } catch { /* use status text */ }
          setMessages((prev) =>
            prev.map((m) =>
              m.id === agentId
                ? errorMessage(agentId, `Query failed (${detail})`, context, thread)
                : m,
            ),
          )
          setBusy(false)
          return
        }

        let data: Record<string, unknown>
        try {
          data = (await resp.json()) as Record<string, unknown>
        } catch {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === agentId
                ? errorMessage(agentId, 'Server returned an unexpected response format.', context, thread)
                : m,
            ),
          )
          setBusy(false)
          return
        }

        responseText = String(data['report'] ?? data['message'] ?? JSON.stringify(data))
      } catch (err) {
        const msg = err instanceof Error ? err.message : String(err)
        setMessages((prev) =>
          prev.map((m) =>
            m.id === agentId ? errorMessage(agentId, `Unexpected error: ${msg}`, context, thread) : m,
          ),
        )
        setBusy(false)
        return
      }

      // stream words into the bubble
      const words = responseText.split(' ')
      let accumulated = ''
      for (const word of words) {
        accumulated += (accumulated ? ' ' : '') + word
        const snap = accumulated
        setMessages((prev) => prev.map((m) => (m.id === agentId ? { ...m, content: snap } : m)))
        await sleep(15)
      }

      const followUps = isError ? [] : deriveFollowUps(context)
      setMessages((prev) =>
        prev.map((m) => (m.id === agentId ? { ...m, streaming: false, isError, followUps } : m)),
      )
      setBusy(false)
    },
    [busy, getMutations],
  )

  const clear = useCallback(() => setMessages([]), [])

  return { messages, busy, send, clear }
}
