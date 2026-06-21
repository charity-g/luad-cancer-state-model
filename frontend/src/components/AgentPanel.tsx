import { useRef, useEffect, useState, useCallback, KeyboardEvent } from 'react'
import type { MutationEntry, ContextCard, EffectType } from '../types'
import type { ChatMessage } from '../hooks/useChat'
import SubgraphView from './SubgraphView'
import MutationDetail from './MutationDetail'

// ── helpers ──────────────────────────────────────────────────────────────────

const effectColors: Record<EffectType, string> = {
  activating:       'bg-amber-100 text-amber-800 border-amber-200',
  gain_of_function: 'bg-amber-100 text-amber-800 border-amber-200',
  inactivating:     'bg-red-100 text-red-800 border-red-200',
  loss_of_function: 'bg-red-100 text-red-800 border-red-200',
  uncertain:        'bg-purple-100 text-purple-700 border-purple-200',
  no_effect:        'bg-slate-100 text-slate-600 border-slate-200',
}
const effectDot: Record<EffectType, string> = {
  activating:       'bg-amber-400',
  gain_of_function: 'bg-amber-500',
  inactivating:     'bg-red-400',
  loss_of_function: 'bg-red-500',
  uncertain:        'bg-purple-400',
  no_effect:        'bg-slate-400',
}
const effectShort: Record<EffectType, string> = {
  activating:       'ACT',
  gain_of_function: 'GOF',
  inactivating:     'INACT',
  loss_of_function: 'LOF',
  uncertain:        'UNC',
  no_effect:        'NONE',
}

function renderContent(text: string) {
  return text.split(/(\*\*[^*]+\*\*|\n)/g).map((part, i) => {
    if (part.startsWith('**') && part.endsWith('**'))
      return <strong key={i} className="font-semibold text-slate-800">{part.slice(2, -2)}</strong>
    if (part === '\n') return <br key={i} />
    return <span key={i}>{part}</span>
  })
}

// ── sub-components ────────────────────────────────────────────────────────────

function ErrorBanner({ message, onDismiss }: { message: string; onDismiss?: () => void }) {
  return (
    <div className="mx-3 my-2 flex items-start gap-2 rounded-lg border border-red-200 bg-red-50 px-3 py-2.5 text-xs text-red-700">
      <svg className="mt-0.5 h-3.5 w-3.5 flex-shrink-0 text-red-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
          d="M12 9v2m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
      </svg>
      <p className="flex-1 leading-relaxed">{message}</p>
      {onDismiss && (
        <button onClick={onDismiss} className="ml-1 flex-shrink-0 opacity-50 hover:opacity-100">
          <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      )}
    </div>
  )
}

function ContextChip({ card, onRemove }: { card: ContextCard; onRemove: () => void }) {
  return (
    <div className={`flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium ${effectColors[card.effect]}`}>
      <span className={`h-1.5 w-1.5 flex-shrink-0 rounded-full ${effectDot[card.effect]}`} />
      <span className="font-semibold">{card.protein}</span>
      <span className="opacity-60">·</span>
      <span>{effectShort[card.effect]}</span>
      {card.pathway && <><span className="opacity-60">·</span><span className="opacity-80">{card.pathway}</span></>}
      <button onClick={onRemove} className="ml-1 opacity-50 hover:opacity-100">
        <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
        </svg>
      </button>
    </div>
  )
}

function ThreadGroup({
  thread, msgs, onFollowUp,
}: {
  thread: string
  msgs: ChatMessage[]
  onFollowUp: (text: string) => void
}) {
  return (
    <div className="mb-4">
      <div className="mb-2 flex items-center gap-2 px-4">
        <span className="h-px flex-1 bg-slate-100" />
        <span className="text-[10px] font-semibold uppercase tracking-widest text-slate-400">{thread}</span>
        <span className="h-px flex-1 bg-slate-100" />
      </div>

      <div className="space-y-3 px-3">
        {msgs.map((msg) => (
          <div key={msg.id}>
            {msg.role === 'user' ? (
              <div className="flex justify-end">
                <div className="max-w-[85%]">
                  {msg.context.length > 0 && (
                    <div className="mb-1 flex flex-wrap justify-end gap-1">
                      {msg.context.map((c) => (
                        <span key={c.id} className={`rounded-full border px-2 py-0.5 text-[10px] font-medium ${effectColors[c.effect] ?? 'bg-slate-100 text-slate-600 border-slate-200'}`}>
                          {c.protein}
                        </span>
                      ))}
                    </div>
                  )}
                  <div className="rounded-2xl rounded-tr-sm bg-slate-900 px-3.5 py-2 text-sm text-white">
                    {msg.content}
                  </div>
                </div>
              </div>
            ) : msg.isError ? (
              /* error bubble */
              <div className="flex gap-2">
                <div className="mt-1 flex h-5 w-5 flex-shrink-0 items-center justify-center rounded-full bg-red-50">
                  <svg className="h-3 w-3 text-red-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                      d="M12 9v2m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
                  </svg>
                </div>
                <div className="flex-1 min-w-0 rounded-2xl rounded-tl-sm border border-red-100 bg-red-50 px-3.5 py-2.5 text-xs leading-relaxed text-red-700">
                  {msg.content}
                </div>
              </div>
            ) : (
              /* normal agent bubble */
              <div className="flex gap-2">
                <div className="mt-1 flex h-5 w-5 flex-shrink-0 items-center justify-center rounded-full bg-blue-50">
                  <svg className="h-3 w-3 text-blue-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                      d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                  </svg>
                </div>
                <div className="flex-1 min-w-0">
                  <div className="rounded-2xl rounded-tl-sm bg-slate-50 px-3.5 py-2.5 text-sm leading-relaxed text-slate-700">
                    {msg.streaming && msg.content === '' ? (
                      <span className="flex gap-1">
                        {[0, 1, 2].map((i) => (
                          <span key={i} className="h-1.5 w-1.5 rounded-full bg-slate-300 animate-bounce"
                            style={{ animationDelay: `${i * 0.15}s` }} />
                        ))}
                      </span>
                    ) : renderContent(msg.content)}
                    {msg.streaming && msg.content !== '' && (
                      <span className="ml-1 inline-block h-3.5 w-0.5 animate-pulse bg-slate-400 align-middle" />
                    )}
                  </div>
                  {!msg.streaming && msg.subgraph && msg.subgraph.nodes.length > 0 && (
                    <SubgraphView subgraph={msg.subgraph} />
                  )}
                  {!msg.streaming && msg.followUps && msg.followUps.length > 0 && (
                    <div className="mt-2 space-y-1">
                      {msg.followUps.map((f) => (
                        <button key={f} onClick={() => onFollowUp(f)}
                          className="block w-full rounded-lg border border-slate-200 px-3 py-1.5 text-left text-xs text-slate-500 hover:border-slate-300 hover:bg-slate-50 hover:text-slate-700 transition-colors">
                          {f}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

// ── main panel ────────────────────────────────────────────────────────────────

interface Props {
  mutations: MutationEntry[]
  selected: string | null
  onSelect: (id: string) => void
  phase: 'idle' | 'streaming' | 'done' | 'error'
  analysisError: string | null
  onDismissError: () => void
  filename: string
  messages: ChatMessage[]
  busy: boolean
  onSend: (text: string, context: ContextCard[]) => void
  onStop: () => void
  onRetry: () => void
  pendingContext: ContextCard | null
  onClearPendingContext: () => void
}

export default function AgentPanel({
  mutations, selected, onSelect, phase, analysisError, onDismissError, filename,
  messages, busy, onSend, onStop, onRetry, pendingContext, onClearPendingContext,
}: Props) {
  const panelRef  = useRef<HTMLDivElement>(null)
  const dragging  = useRef(false)
  const [splitPct, setSplitPct] = useState(38)

  const onMouseMove = useCallback((e: MouseEvent) => {
    if (!dragging.current || !panelRef.current) return
    const rect = panelRef.current.getBoundingClientRect()
    setSplitPct(Math.max(20, Math.min(65, ((e.clientY - rect.top) / rect.height) * 100)))
  }, [])
  const onMouseUp = useCallback(() => { dragging.current = false }, [])

  useEffect(() => {
    window.addEventListener('mousemove', onMouseMove)
    window.addEventListener('mouseup', onMouseUp)
    return () => {
      window.removeEventListener('mousemove', onMouseMove)
      window.removeEventListener('mouseup', onMouseUp)
    }
  }, [onMouseMove, onMouseUp])

  const [contextCards, setContextCards] = useState<ContextCard[]>([])
  const scrollRef = useRef<HTMLDivElement>(null)
  const inputRef  = useRef<HTMLInputElement>(null)
  const [draft, setDraft] = useState('')

  useEffect(() => {
    if (!pendingContext) return
    setContextCards((prev) => prev.find((c) => c.id === pendingContext.id) ? prev : [...prev, pendingContext])
    onClearPendingContext()
    inputRef.current?.focus()
  }, [pendingContext, onClearPendingContext])

  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight
  }, [messages])

  function handleSend() {
    if (!draft.trim() || busy) return
    onSend(draft.trim(), contextCards)
    setDraft('')
    setContextCards([])
  }

  const lastMsg = messages[messages.length - 1]
  const canRetry = !busy && !!lastMsg && lastMsg.role === 'agent' && (!!lastMsg.isError || !!lastMsg.stopped)

  function handleKey(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend() }
  }

  const threads: Array<{ label: string; msgs: ChatMessage[] }> = []
  for (const msg of messages) {
    const last = threads[threads.length - 1]
    if (last && last.label === msg.thread) last.msgs.push(msg)
    else threads.push({ label: msg.thread, msgs: [msg] })
  }

  const done = mutations.filter((m) => m.status === 'done').length

  return (
    <div ref={panelRef} className="flex h-full w-80 flex-shrink-0 flex-col border-l border-slate-200 bg-white">

      {/* ── TOP: Mutation list / detail ───────────────────────── */}
      <div className="flex flex-col overflow-hidden" style={{ height: `${splitPct}%` }}>
        {selected ? (
          /* ── Detail view ── */
          <>
            <div className="flex flex-shrink-0 items-center gap-2 border-b border-slate-100 px-3 py-2">
              <button
                onClick={() => onSelect('')}
                className="flex items-center gap-1 rounded p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600"
                title="Back to list"
              >
                <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
                </svg>
              </button>
              <p className="text-xs font-semibold text-slate-700">Mutation detail</p>
            </div>
            <MutationDetail entry={mutations.find((m) => m.mutation_id === selected)} />
          </>
        ) : (
          /* ── List view ── */
          <>
            <div className="flex flex-shrink-0 items-center justify-between border-b border-slate-100 px-4 py-2.5">
              <div>
                <p className="text-xs font-semibold text-slate-700">Mutations</p>
                <p className="text-[11px] text-slate-400">
                  {phase === 'error' ? (
                    <span className="text-red-500">Analysis failed</span>
                  ) : (
                    <>
                      {mutations.length} variant{mutations.length !== 1 ? 's' : ''}
                      {phase === 'streaming' && ' · analyzing…'}
                      {phase === 'done' && ` · ${done} annotated`}
                    </>
                  )}
                </p>
              </div>
              {phase === 'streaming' && (
                <div className="h-4 w-4 animate-spin rounded-full border-2 border-slate-200 border-t-blue-500" />
              )}
              {phase === 'error' && (
                <svg className="h-4 w-4 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                    d="M12 9v2m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
                </svg>
              )}
            </div>

            {phase === 'streaming' && mutations.length > 0 && (
              <div className="h-0.5 w-full bg-slate-100">
                <div className="h-full bg-blue-500 transition-all duration-300"
                  style={{ width: `${(done / mutations.length) * 100}%` }} />
              </div>
            )}

            {phase === 'error' && analysisError && (
              <ErrorBanner message={analysisError} onDismiss={onDismissError} />
            )}

            <ul className="flex-1 divide-y divide-slate-100 overflow-y-auto">
              {mutations.length === 0 && phase === 'streaming' && (
                <li className="flex flex-col items-center justify-center py-8 text-slate-400">
                  <div className="h-4 w-4 animate-spin rounded-full border-2 border-slate-200 border-t-blue-500" />
                  <p className="mt-2 text-xs">Identifying variants…</p>
                </li>
              )}
              {mutations.length === 0 && phase === 'error' && !analysisError && (
                <li className="flex flex-col items-center justify-center py-8 text-slate-400">
                  <p className="text-xs">No variants were loaded.</p>
                </li>
              )}
              {mutations.map((m) => (
                <li key={m.mutation_id}>
                  <button
                    onClick={() => onSelect(m.mutation_id)}
                    className="w-full px-4 py-2 text-left transition-colors hover:bg-slate-50"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="min-w-0 truncate font-mono text-xs font-medium text-slate-700">
                        {m.mutation_id}
                      </span>
                      {m.status === 'done' && m.hydrated && (
                        <span className={`flex-shrink-0 rounded border px-1.5 py-0.5 text-[10px] font-semibold ${effectColors[m.hydrated.estimated_effect as EffectType] ?? 'bg-slate-100 text-slate-600 border-slate-200'}`}>
                          {effectShort[m.hydrated.estimated_effect as EffectType] ?? m.hydrated.estimated_effect.slice(0, 4).toUpperCase()}
                        </span>
                      )}
                      {m.status === 'hydrating' && (
                        <span className="h-3 w-3 flex-shrink-0 animate-spin rounded-full border-2 border-slate-200 border-t-blue-400" />
                      )}
                      {m.status === 'failed' && (
                        <span className="flex-shrink-0 rounded border border-red-200 bg-red-50 px-1.5 py-0.5 text-[10px] font-semibold text-red-500">
                          ERR
                        </span>
                      )}
                    </div>
                    {m.hydrated && (
                      <p className="mt-0.5 text-[11px] text-slate-400">{m.hydrated.protein}</p>
                    )}
                    {m.status === 'failed' && m.error && (
                      <p className="mt-0.5 line-clamp-1 text-[11px] text-red-400">{m.error}</p>
                    )}
                  </button>
                </li>
              ))}
            </ul>
          </>
        )}
      </div>

      {/* ── DRAG HANDLE ─────────────────────────────────────────── */}
      <div
        className="group flex h-3 flex-shrink-0 cursor-row-resize items-center justify-center border-y border-slate-100 bg-slate-50 hover:bg-slate-100"
        onMouseDown={() => { dragging.current = true }}
      >
        <div className="flex gap-0.5">
          {[0, 1, 2].map((i) => (
            <div key={i} className="h-0.5 w-4 rounded-full bg-slate-300 group-hover:bg-slate-400" />
          ))}
        </div>
      </div>

      {/* ── BOTTOM: Agent chat ───────────────────────────────────── */}
      <div className="flex flex-1 flex-col overflow-hidden">
        <div className="flex flex-shrink-0 items-center gap-2 border-b border-slate-100 px-4 py-2">
          <svg className="h-3.5 w-3.5 text-blue-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
              d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
          </svg>
          <p className="text-xs font-semibold text-slate-700">Agent Workspace</p>
          {filename && <p className="ml-auto truncate text-[10px] text-slate-400">{filename}</p>}
        </div>

        <div ref={scrollRef} className="flex-1 overflow-y-auto py-3">
          {threads.length === 0 ? (
            <div className="flex flex-col items-center justify-center px-6 py-10 text-center text-slate-400">
              <svg className="mb-2 h-7 w-7 opacity-40" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                  d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
              </svg>
              <p className="text-xs">Click a protein node or mutation to add context, then ask the agent.</p>
            </div>
          ) : (
            threads.map((t) => (
              <ThreadGroup
                key={t.label + t.msgs[0]?.id}
                thread={t.label}
                msgs={t.msgs}
                onFollowUp={(text) => { setDraft(text); inputRef.current?.focus() }}
              />
            ))
          )}
        </div>

        {/* context tray */}
        {contextCards.length > 0 && (
          <div className="border-t border-slate-100 bg-slate-50 px-3 py-2">
            <p className="mb-1.5 text-[10px] font-medium uppercase tracking-wider text-slate-400">Context</p>
            <div className="flex flex-wrap gap-1.5">
              {contextCards.map((c) => (
                <ContextChip key={c.id} card={c}
                  onRemove={() => setContextCards((prev) => prev.filter((x) => x.id !== c.id))} />
              ))}
            </div>
          </div>
        )}

        {/* input */}
        <div className="flex-shrink-0 border-t border-slate-100 px-3 py-2.5">
          <div className="flex items-center gap-2">
            <input
              ref={inputRef}
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={handleKey}
              disabled={busy}
              placeholder={contextCards.length > 0 ? 'Ask follow-up…' : busy ? 'Agent is thinking…' : 'Ask about this dataset…'}
              className="flex-1 rounded-xl border border-slate-200 bg-slate-50 px-3.5 py-2 text-xs text-slate-800 placeholder-slate-400 outline-none focus:border-slate-300 focus:bg-white disabled:opacity-50"
            />
            {canRetry && (
              <button
                onClick={onRetry}
                title="Retry last question"
                className="flex h-8 flex-shrink-0 items-center rounded-xl border border-slate-200 px-2.5 text-xs text-slate-500 hover:bg-slate-50 hover:text-slate-700"
              >
                ↻ Retry
              </button>
            )}
            {busy ? (
              <button
                onClick={onStop}
                title="Stop generating"
                className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-xl bg-rose-600 text-white transition-colors hover:bg-rose-500"
              >
                <svg className="h-3 w-3" viewBox="0 0 24 24" fill="currentColor">
                  <rect x="6" y="6" width="12" height="12" rx="2" />
                </svg>
              </button>
            ) : (
              <button
                onClick={handleSend}
                disabled={!draft.trim()}
                className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-xl bg-slate-900 text-white transition-colors hover:bg-slate-700 disabled:opacity-30"
              >
                <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 12h14M12 5l7 7-7 7" />
                </svg>
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
