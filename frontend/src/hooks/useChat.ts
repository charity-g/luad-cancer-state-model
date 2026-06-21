import { useState, useCallback, useRef, useEffect } from 'react'
import type { HydratedMutation, ContextCard, Subgraph, DrugHit } from '../types'
import {
  saveConversation,
  loadConversation,
  listConversations,
  type ConversationRecord,
} from '../db/conversations'

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
  drugs?: DrugHit[]
  mode?: 'lookup' | 'reason'
  verdict?: string
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

export function useChat(getMutations: () => HydratedMutation[], profileId?: string | null) {
  const [messages, setMessages]   = useState<ChatMessage[]>([])
  const [sessions, setSessions]   = useState<ConversationRecord[]>([])
  const [sessionId, setSessionId] = useState<string>(() => uid())
  const sessionCreatedAt          = useRef<number>(Date.now())

  const [busy, setBusy]       = useState(false)
  const abortRef              = useRef<AbortController | null>(null)
  const lastRef               = useRef<{ text: string; context: ContextCard[] } | null>(null)
  const messagesRef           = useRef<ChatMessage[]>(messages)

  // Keep ref in sync
  useEffect(() => { messagesRef.current = messages }, [messages])

  // When profileId changes, load its sessions and restore the most recent one
  useEffect(() => {
    if (!profileId) {
      setSessions([])
      setMessages([])
      setSessionId(uid())
      sessionCreatedAt.current = Date.now()
      return
    }
    listConversations(profileId).then((rows) => {
      setSessions(rows)
      if (rows.length > 0) {
        const latest = rows[0]
        setSessionId(latest.session_id)
        setMessages(latest.messages)
        sessionCreatedAt.current = latest.created_at
      } else {
        setSessionId(uid())
        setMessages([])
        sessionCreatedAt.current = Date.now()
      }
    })
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [profileId])

  // Persist to IndexedDB whenever messages change
  useEffect(() => {
    if (!profileId || messages.length === 0) return
    const rec: ConversationRecord = {
      session_id:  sessionId,
      profile_id:  profileId,
      created_at:  sessionCreatedAt.current,
      updated_at:  Date.now(),
      title:       messages.find((m) => m.role === 'user')?.content.slice(0, 60) ?? 'New conversation',
      messages,
    }
    saveConversation(rec).then(() =>
      listConversations(profileId).then(setSessions)
    )
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [messages])

  const switchSession = useCallback(async (id: string) => {
    const rec = await loadConversation(id)
    if (!rec) return
    setSessionId(rec.session_id)
    setMessages(rec.messages)
    sessionCreatedAt.current = rec.created_at
  }, [])

  const newSession = useCallback(() => {
    const id = uid()
    setSessionId(id)
    setMessages([])
    sessionCreatedAt.current = Date.now()
  }, [])

  const send = useCallback(
    async (text: string, context: ContextCard[]) => {
      if (!text.trim() || busy) return
      lastRef.current = { text: text.trim(), context }

      const ac = new AbortController()
      abortRef.current = ac

      const thread = deriveThread(context)
      const history = messagesRef.current
        .filter((m) => !m.isError && m.content && m.thread === thread)
        .map((m) => ({ role: m.role, content: m.content }))

      const userMsg: ChatMessage  = { id: uid(), role: 'user', content: text.trim(), context, thread }
      const agentId               = uid()
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
          resp = await fetch('/api/query', {
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
    [busy, getMutations, profileId],
  )

  const stop = useCallback(() => {
    abortRef.current?.abort()
  }, [])

  const retry = useCallback(() => {
    if (lastRef.current && !busy) send(lastRef.current.text, lastRef.current.context)
  }, [busy, send])

  const clear = useCallback(() => {
    newSession()
  }, [newSession])

  return { messages, busy, send, stop, retry, clear, sessions, sessionId, switchSession, newSession }
}
