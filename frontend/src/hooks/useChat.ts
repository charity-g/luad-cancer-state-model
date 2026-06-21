import { useState, useCallback, useRef, useEffect } from 'react'
import type { HydratedMutation, ContextCard, Subgraph, DrugHit } from '../types'
import { API_BASE } from '../lib/api'

export interface ChatMessage {
  id: string
  role: 'user' | 'agent'
  content: string
  streaming?: boolean
  isError?: boolean
  stopped?: boolean
  context: ContextCard[]
  thread: string
  followUps?: string[]
  subgraph?: Subgraph
  drugs?: DrugHit[]   // TTD drug hits returned by this agent turn
  mode?: 'lookup' | 'reason'  // which pipeline path ran
  verdict?: string    // short clinical verdict from the reasoning agent
}

function storageKey(profileId: string | null | undefined) {
  return profileId ? `luad_chat_${profileId}` : null
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

function loadHistory(key: string): ChatMessage[] {
  try {
    const raw = localStorage.getItem(key)
    return raw ? (JSON.parse(raw) as ChatMessage[]) : []
  } catch {
    return []
  }
}

export function useChat(getMutations: () => HydratedMutation[], profileId?: string | null) {
  const key = storageKey(profileId)

  const [messages, setMessages] = useState<ChatMessage[]>(() =>
    key ? loadHistory(key) : []
  )
  const [busy, setBusy] = useState(false)
  const abortRef = useRef<AbortController | null>(null)
  const lastRef = useRef<{ text: string; context: ContextCard[] } | null>(null)
  const messagesRef = useRef<ChatMessage[]>(messages)

  // Swap to the profile-specific history whenever the active profile changes.
  useEffect(() => {
    setMessages(key ? loadHistory(key) : [])
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key])

  // Persist to the profile-specific key on every change.
  useEffect(() => {
    messagesRef.current = messages
    if (!key) return
    try {
      localStorage.setItem(key, JSON.stringify(messages))
    } catch {
      /* storage full / unavailable — non-fatal */
    }
  }, [messages, key])

  const send = useCallback(
    async (text: string, context: ContextCard[]) => {
      if (!text.trim() || busy) return
      lastRef.current = { text: text.trim(), context }

      const ac = new AbortController()
      abortRef.current = ac

      const thread = deriveThread(context)
      // Memory is scoped to the current selection's thread, so switching nodes
      // (e.g. KRAS -> mTOR) doesn't drag the previous topic into the answer.
      const history = messagesRef.current
        .filter((m) => !m.isError && m.content && m.thread === thread)
        .map((m) => ({ role: m.role, content: m.content }))

      const userMsg: ChatMessage = { id: uid(), role: 'user', content: text.trim(), context, thread }
      const agentId = uid()
      const agentMsg: ChatMessage = { id: agentId, role: 'agent', content: '', streaming: true, context, thread }

      setMessages((prev) => [...prev, userMsg, agentMsg])
      setBusy(true)

      const fail = (msg: string) => {
        setMessages((prev) => prev.map((m) => (m.id === agentId ? errorMessage(agentId, msg, context, thread) : m)))
        setBusy(false)
        abortRef.current = null
      }
      const markStopped = (partial: string) => {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === agentId
              ? { ...m, content: partial || '_(stopped)_', streaming: false, stopped: true }
              : m,
          ),
        )
        setBusy(false)
        abortRef.current = null
      }

      let responseText = ''
      let subgraph: Subgraph | undefined
      let drugs: DrugHit[] = []
      let mode: 'lookup' | 'reason' | undefined
      let verdict: string | undefined
      try {
        const mutations = getMutations()
        let resp: Response
        try {
          resp = await fetch(`${API_BASE}/api/query`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            signal: ac.signal,
            body: JSON.stringify({
              question: text.trim(),
              profile_id: profileId ?? null,
              context: context.map((c) => ({ ...c })),
              history,
              mutations: mutations.map((m) => ({
                mutation_id: m.mutation_id,
                protein: m.protein,
                estimated_effect: m.estimated_effect,
                justification: m.justification,
                hgvs_protein: m.hgvs_protein,
                gene: m.gene,
                features: m.features,
              })),
            }),
          })
        } catch (e) {
          if (ac.signal.aborted) return markStopped('')
          fail('Cannot reach the backend — is the server running on port 8000?')
          return
        }

        if (!resp.ok) {
          let detail = `${resp.status} ${resp.statusText}`
          try {
            const errBody = (await resp.json()) as Record<string, unknown>
            detail = String(errBody['detail'] ?? errBody['message'] ?? detail)
          } catch { /* use status text */ }
          fail(`Query failed (${detail})`)
          return
        }

        let data: Record<string, unknown>
        try {
          data = (await resp.json()) as Record<string, unknown>
        } catch {
          fail('Server returned an unexpected response format.')
          return
        }
        responseText = String(data['report'] ?? data['message'] ?? JSON.stringify(data))
        const sg = data['subgraph'] as Subgraph | undefined
        if (sg && Array.isArray(sg.nodes) && sg.nodes.length) subgraph = sg
        const rawDrugs = data['ttd_drugs']
        drugs = Array.isArray(rawDrugs) && rawDrugs.length ? rawDrugs as DrugHit[] : []
        mode = (data['mode'] === 'lookup' || data['mode'] === 'reason') ? data['mode'] : undefined
        verdict = data['verdict'] ? String(data['verdict']) : undefined
      } catch (err) {
        if (ac.signal.aborted) return markStopped('')
        const msg = err instanceof Error ? err.message : String(err)
        fail(`Unexpected error: ${msg}`)
        return
      }

      // Stream words into the bubble; stop() interrupts this too.
      const words = responseText.split(' ')
      let accumulated = ''
      for (const word of words) {
        if (ac.signal.aborted) return markStopped(accumulated)
        accumulated += (accumulated ? ' ' : '') + word
        const snap = accumulated
        setMessages((prev) => prev.map((m) => (m.id === agentId ? { ...m, content: snap } : m)))
        await sleep(15)
      }

      const followUps = deriveFollowUps(context)
      setMessages((prev) =>
        prev.map((m) => (m.id === agentId ? { ...m, streaming: false, followUps, subgraph, drugs: drugs.length ? drugs : undefined, mode, verdict } : m)),
      )
      setBusy(false)
      abortRef.current = null
    },
    [busy, getMutations],
  )

  const stop = useCallback(() => {
    abortRef.current?.abort()
  }, [])

  const retry = useCallback(() => {
    if (lastRef.current && !busy) send(lastRef.current.text, lastRef.current.context)
  }, [busy, send])

  const clear = useCallback(() => {
    setMessages([])
    try {
      if (key) localStorage.removeItem(key)
    } catch { /* non-fatal */ }
  }, [key])

  return { messages, busy, send, stop, retry, clear }
}
