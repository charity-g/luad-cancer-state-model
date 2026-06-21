import { useRef, useEffect, useState, KeyboardEvent } from 'react'
import type { ChatMessage } from '../hooks/useChat'

interface Props {
  messages: ChatMessage[]
  busy: boolean
  onSend: (text: string) => void
  onNewFile: () => void
  filename: string
}

function renderContent(text: string) {
  // Bold **text**, newlines → <br>
  const parts = text.split(/(\*\*[^*]+\*\*|\n)/g)
  return parts.map((part, i) => {
    if (part.startsWith('**') && part.endsWith('**')) {
      return <strong key={i} className="font-semibold text-slate-100">{part.slice(2, -2)}</strong>
    }
    if (part === '\n') return <br key={i} />
    return <span key={i}>{part}</span>
  })
}

export default function ChatBox({ messages, busy, onSend, onNewFile, filename }: Props) {
  const [draft, setDraft] = useState('')
  const [expanded, setExpanded] = useState(false)
  const scrollRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  // Auto-expand when first message arrives
  useEffect(() => {
    if (messages.length > 0) setExpanded(true)
  }, [messages.length])

  // Scroll to bottom on new messages
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [messages])

  function handleSend() {
    if (!draft.trim() || busy) return
    onSend(draft.trim())
    setDraft('')
  }

  function handleKey(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <div className="flex flex-shrink-0 flex-col border-t border-slate-200 bg-white">
      {/* Chat history — collapsible */}
      {expanded && messages.length > 0 && (
        <div
          ref={scrollRef}
          className="max-h-64 overflow-y-auto border-b border-slate-100 px-4 py-3 space-y-3"
        >
          {messages.map((msg) => (
            <div key={msg.id} className={`flex gap-2.5 ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
              {msg.role === 'agent' && (
                <div className="mt-0.5 flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-full bg-slate-100">
                  <svg className="h-3.5 w-3.5 text-slate-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                      d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                  </svg>
                </div>
              )}
              <div
                className={`max-w-lg rounded-2xl px-3.5 py-2 text-sm leading-relaxed ${
                  msg.role === 'user'
                    ? 'bg-slate-900 text-white'
                    : 'bg-slate-100 text-slate-700'
                }`}
              >
                {msg.role === 'agent' ? renderContent(msg.content) : msg.content}
                {msg.streaming && (
                  <span className="ml-1 inline-block h-3.5 w-0.5 animate-pulse bg-slate-400 align-middle" />
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Input row */}
      <div className="flex items-center gap-2 px-4 py-3">
        {/* Collapse / expand toggle when there are messages */}
        {messages.length > 0 && (
          <button
            onClick={() => setExpanded((v) => !v)}
            className="flex-shrink-0 rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-600"
            title={expanded ? 'Collapse chat' : 'Expand chat'}
          >
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d={expanded ? 'M19 9l-7 7-7-7' : 'M5 15l7-7 7 7'} />
            </svg>
          </button>
        )}

        <input
          ref={inputRef}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={handleKey}
          placeholder={busy ? 'Agent is thinking…' : `Ask about ${filename}…`}
          disabled={busy}
          className="flex-1 rounded-xl border border-slate-200 bg-slate-50 px-4 py-2.5 text-sm text-slate-800 placeholder-slate-400 outline-none focus:border-slate-400 focus:bg-white disabled:opacity-50"
        />

        <button
          onClick={handleSend}
          disabled={!draft.trim() || busy}
          className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-xl bg-slate-900 text-white transition-colors hover:bg-slate-700 disabled:opacity-30"
        >
          {busy ? (
            <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-white/30 border-t-white" />
          ) : (
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 12h14M12 5l7 7-7 7" />
            </svg>
          )}
        </button>

        <button
          onClick={onNewFile}
          className="flex-shrink-0 rounded-xl border border-slate-200 px-3 py-2 text-xs text-slate-500 hover:bg-slate-50 hover:text-slate-700"
          title="Upload new file"
        >
          New file
        </button>
      </div>
    </div>
  )
}
