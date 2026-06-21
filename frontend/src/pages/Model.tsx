import { useState, useCallback, useMemo, useEffect, useRef, type KeyboardEvent } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useAnalysis } from '../hooks/useAnalysis'
import { useProfileGraph } from '../hooks/useProfileGraph'
import { useChat, type ChatMessage } from '../hooks/useChat'
import UploadBox from '../components/UploadBox'
import AgentPanel from '../components/AgentPanel'
import PathwayGraph from '../components/PathwayGraph'
import SubgraphView from '../components/SubgraphView'
import DrugPanel from '../components/DrugPanel'
import DrugCarousel from '../components/DrugCarousel'
import StructureModal, { type StructureTarget } from '../components/StructureModal'
import { useProfileDrugs, type ProfileDrug } from '../hooks/useProfileDrugs'
import type { HydratedMutation, ContextCard, DrugHit, SubgraphNode, EffectType } from '../types'

type GraphTab = 'pathway' | 'agent' | 'drugs'

const STARTER_PROMPTS = [
  'What pathways are activated in lung adenocarcinoma?',
  'How does EGFR mutation affect downstream signaling?',
  'Which drugs target KRAS G12C?',
  'Explain the role of P53 in tumor suppression.',
]

function IdleSplash({
  onFile, messages, busy, onSend, onStop, onClear,
}: {
  onFile: (f: File) => void
  messages: ChatMessage[]
  busy: boolean
  onSend: (text: string) => void
  onStop: () => void
  onClear: () => void
}) {
  const chatRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const [draft, setDraft] = useState('')

  useEffect(() => {
    if (chatRef.current) chatRef.current.scrollTop = chatRef.current.scrollHeight
  }, [messages])

  function handleSend() {
    if (!draft.trim() || busy) return
    onSend(draft.trim())
    setDraft('')
  }

  function handleKey(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend() }
  }

  return (
    <div className="flex flex-1 flex-col overflow-hidden">
      {/* Top splash */}
      <div className="flex flex-1 flex-col items-center justify-center px-6 text-center">
        <svg className="mb-4 h-12 w-12 text-slate-300" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1}
            d="M9 3H5a2 2 0 00-2 2v4m6-6h10a2 2 0 012 2v4M9 3v18m0 0h10a2 2 0 002-2V9M9 21H5a2 2 0 01-2-2V9m0 0h18" />
        </svg>
        <h2 className="text-lg font-semibold text-slate-700">Scientific Reasoning Workspace</h2>
        <p className="mt-2 max-w-lg text-sm text-slate-400">
          Upload a mutation profile to visualize affected pathways, or ask the agent
          questions about lung cancer biology directly.
        </p>
      </div>

      {/* Bottom half: Upload (left) + Chat (right) */}
      <div className="flex h-1/2 flex-shrink-0 border-t border-slate-200">
        {/* LEFT: Upload */}
        <div className="flex w-1/2 flex-col border-r border-slate-200 bg-white">
          <div className="flex items-center gap-2 border-b border-slate-100 px-4 py-2.5">
            <svg className="h-4 w-4 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
            </svg>
            <span className="text-xs font-semibold text-slate-700">Upload Mutation Profile</span>
          </div>
          <div className="flex flex-1 items-center justify-center p-4">
            <UploadBox onFile={onFile} hasData={false} standalone />
          </div>
        </div>

        {/* RIGHT: Chat */}
        <div className="flex w-1/2 flex-col bg-white">
          <div className="flex items-center gap-2 border-b border-slate-100 px-4 py-2.5">
            <svg className="h-4 w-4 text-blue-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
            </svg>
            <span className="text-xs font-semibold text-slate-700">Ask the Agent</span>
            {messages.length > 0 && (
              <button
                onClick={onClear}
                className="ml-auto flex items-center gap-1 rounded-md px-2 py-1 text-[10px] text-slate-400 hover:bg-slate-100 hover:text-slate-600 transition-colors"
                title="Clear chat"
              >
                <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                    d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                </svg>
                Clear
              </button>
            )}
          </div>

          <div ref={chatRef} className="flex-1 overflow-y-auto px-4 py-3 space-y-3">
            {messages.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full text-center">
                <p className="text-xs text-slate-400 mb-3">Ask about LUAD pathways, mutations, or drug targets</p>
                <div className="space-y-1.5 w-full max-w-sm">
                  {STARTER_PROMPTS.map((prompt) => (
                    <button
                      key={prompt}
                      onClick={() => { setDraft(prompt); inputRef.current?.focus() }}
                      className="block w-full rounded-lg border border-slate-200 px-3 py-2 text-left text-xs text-slate-500 hover:border-slate-300 hover:bg-slate-50 hover:text-slate-700 transition-colors"
                    >
                      {prompt}
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              messages.map((msg) => (
                <div key={msg.id} className={`flex gap-2 ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                  {msg.role === 'agent' && (
                    <div className="mt-1 flex h-5 w-5 flex-shrink-0 items-center justify-center rounded-full bg-blue-50">
                      <svg className="h-3 w-3 text-blue-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                          d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                      </svg>
                    </div>
                  )}
                  <div className={`max-w-[85%] rounded-2xl px-3.5 py-2 text-sm leading-relaxed ${
                    msg.role === 'user'
                      ? 'rounded-tr-sm bg-slate-900 text-white'
                      : msg.isError
                        ? 'rounded-tl-sm border border-red-100 bg-red-50 text-xs text-red-700'
                        : 'rounded-tl-sm bg-slate-50 text-slate-700'
                  }`}>
                    {msg.content}
                    {msg.streaming && msg.content !== '' && (
                      <span className="ml-1 inline-block h-3.5 w-0.5 animate-pulse bg-slate-400 align-middle" />
                    )}
                    {msg.streaming && msg.content === '' && (
                      <span className="flex gap-1">
                        {[0, 1, 2].map((i) => (
                          <span key={i} className="h-1.5 w-1.5 rounded-full bg-slate-300 animate-bounce"
                            style={{ animationDelay: `${i * 0.15}s` }} />
                        ))}
                      </span>
                    )}
                  </div>
                </div>
              ))
            )}
          </div>

          <div className="flex-shrink-0 border-t border-slate-100 px-3 py-2.5">
            <div className="flex items-center gap-2">
              <input
                ref={inputRef}
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                onKeyDown={handleKey}
                disabled={busy}
                placeholder={busy ? 'Agent is thinking...' : 'Ask about lung cancer biology...'}
                className="flex-1 rounded-xl border border-slate-200 bg-slate-50 px-3.5 py-2 text-xs text-slate-800 placeholder-slate-400 outline-none focus:border-slate-300 focus:bg-white disabled:opacity-50"
              />
              {busy ? (
                <button
                  onClick={onStop}
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
    </div>
  )
}

export default function Model() {
  const [searchParams, setSearchParams] = useSearchParams()
  // profileId from URL takes precedence (history load); analysis stream may also set one
  const urlProfileId = searchParams.get('profileId')

  const { mutations: streamMutations, phase, error: analysisError, profileId: streamProfileId, analyze, reset, patchMutation } = useAnalysis()
  const activeProfileId = streamProfileId ?? urlProfileId

  // When a profile is loaded from history (URL param, no active stream), pull
  // mutation nodes from the stored graph so the sidebar is populated.
  const isHistoryLoad = !!urlProfileId && phase === 'idle'
  const { mutations: graphMutations, loading: graphLoading } = useProfileGraph(isHistoryLoad ? urlProfileId : null)

  // Active mutation list: stream takes precedence when running, graph fills in on history load
  const mutations = phase !== 'idle' ? streamMutations : graphMutations

  const [selected, setSelected] = useState<string | null>(null)
  const [filename, setFilename] = useState('')
  const [panelVisible, setPanelVisible] = useState(true)
  // Highlights off by default — user must opt in so the graph starts blank
  const [highlightsOn, setHighlightsOn] = useState(false)
  const [pendingContext, setPendingContext] = useState<ContextCard | null>(null)
  const [dismissedError, setDismissedError] = useState(false)
  const [graphTab, setGraphTab] = useState<GraphTab>('pathway')
  const [structureTarget, setStructureTarget] = useState<StructureTarget | null>(null)
  const [drugCarouselOpen, setDrugCarouselOpen] = useState(false)
  const [ppiOn, setPpiOn] = useState(false)

  const { drugs: profileDrugs, loading: drugsLoading } = useProfileDrugs(
    highlightsOn ? activeProfileId : null
  )

  function handleViewStructure(uniprotAc: string, proteinName: string, mutationResidue: number | null) {
    setStructureTarget({ uniprotAc, proteinName, mutationResidue })
  }

  const getHydrated = useCallback(
    (): HydratedMutation[] => mutations.filter((m) => m.hydrated).map((m) => m.hydrated!),
    [mutations],
  )
  const { messages, busy, send, stop, retry, clear, sessions, sessionId, switchSession, newSession } = useChat(getHydrated, activeProfileId)

  // The agent's reasoning graph shown in the "Agent Graph" tab is the most
  // recent answer's subgraph.
  const latestSubgraph = useMemo(() => {
    for (let i = messages.length - 1; i >= 0; i--) {
      const sg = messages[i].subgraph
      if (sg && sg.nodes.length > 0) return { id: messages[i].id, subgraph: sg }
    }
    return null
  }, [messages])

  // Collect all unique drug hits across the session — deduped by drugbank_id.
  const allDrugs = useMemo((): DrugHit[] => {
    const seen = new Set<string>()
    const result: DrugHit[] = []
    for (const msg of messages) {
      for (const d of msg.drugs ?? []) {
        const key = d.drugbank_id || d.drug_name
        if (!seen.has(key)) { seen.add(key); result.push(d) }
      }
    }
    return result
  }, [messages])

  // Auto-switch to the Agent Graph tab when:
  //   - a new graph is generated on any agent turn, OR
  //   - the mode is 'lookup' (graph IS the answer — always show it)
  // Skip the first render so a persisted graph doesn't yank the user on page open.
  const seenSubgraphId = useRef<string | null | undefined>(undefined)
  useEffect(() => {
    const id = latestSubgraph?.id ?? null
    if (seenSubgraphId.current === undefined) {
      seenSubgraphId.current = id
      return
    }
    if (id && id !== seenSubgraphId.current) {
      seenSubgraphId.current = id
      setGraphTab('agent')
    }
  }, [latestSubgraph])

  // For lookup answers: switch to Agent Graph as soon as the message is done streaming.
  const lastMessage = messages[messages.length - 1]
  useEffect(() => {
    if (lastMessage?.role === 'agent' && !lastMessage.streaming && lastMessage.mode === 'lookup') {
      setGraphTab('agent')
    }
  }, [lastMessage?.id, lastMessage?.streaming, lastMessage?.mode])

  function handleFile(file: File) {
    setFilename(file.name)
    setSelected(null)
    setDismissedError(false)
    setHighlightsOn(false)
    // Clear URL profileId so the new stream's profileId takes over
    setSearchParams({})
    analyze(file)
    setPanelVisible(true)
  }

  function handleReset() {
    reset()
    setSelected(null)
    setFilename('')
    setPendingContext(null)
    setDismissedError(false)
    setHighlightsOn(false)
    setGraphTab('pathway')
    setSearchParams({})
    seenSubgraphId.current = null
    clear()
  }

  const hydratedList = mutations.filter((m) => m.hydrated).map((m) => m.hydrated!)
  // Show the workspace if there's an active analysis OR a URL-loaded profileId
  const hasData = phase !== 'idle' || !!urlProfileId
  const visibleError = dismissedError ? null : analysisError

  return (
    <div className="flex h-full flex-col">
      {/* ── Main workspace ──────────────────────────────────────── */}
      <div className="flex flex-1 overflow-hidden">
        {!hasData ? (
          <IdleSplash
            onFile={handleFile}
            messages={messages}
            busy={busy}
            onSend={(text: string) => send(text, [])}
            onStop={stop}
            onClear={clear}
          />
        ) : graphLoading ? (
          <div className="flex flex-1 items-center justify-center gap-2 text-sm text-slate-400">
            <svg className="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
            </svg>
            Loading profile…
          </div>
        ) : (
          // active workspace: graph (center) + agent panel (right)
          <div className="flex flex-1 overflow-hidden">
            {/* ── Graph area ─────────────────────────────────────── */}
            <div className="flex flex-1 flex-col overflow-hidden">
              {/* toolbar */}
              <div className="relative flex flex-shrink-0 flex-col border-b border-slate-700 bg-slate-900">
              <div className="flex items-center gap-3 px-4 py-2">
                {/* graph tabs */}
                <div className="flex items-center rounded-md bg-slate-800 p-0.5">
                  {([
                    { key: 'pathway', label: 'Pathway Network', dot: null },
                    { key: 'agent',   label: 'Agent Graph',     dot: latestSubgraph ? 'bg-emerald-400' : null },
                    ...(allDrugs.length > 0
                      ? [{ key: 'drugs', label: 'Drugs', dot: 'bg-blue-400' }]
                      : []),
                  ] as { key: GraphTab; label: string; dot: string | null }[]).map((t) => (
                    <button
                      key={t.key}
                      onClick={() => setGraphTab(t.key)}
                      className={`flex items-center gap-1.5 rounded px-2.5 py-1 text-xs font-medium transition-colors ${
                        graphTab === t.key
                          ? 'bg-slate-700 text-slate-100'
                          : 'text-slate-400 hover:text-slate-200'
                      }`}
                    >
                      {t.label}
                      {t.dot && <span className={`h-1.5 w-1.5 rounded-full ${t.dot}`} />}
                    </button>
                  ))}
                </div>

                {graphTab === 'pathway' && (
                  <button
                    onClick={() => { setHighlightsOn((v) => !v); setDrugCarouselOpen(false); setPpiOn(false) }}
                    className={`flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-medium transition-colors ${
                      highlightsOn
                        ? 'bg-slate-700 text-slate-200 hover:bg-slate-600'
                        : 'bg-slate-800 text-slate-500 hover:bg-slate-700 hover:text-slate-300'
                    }`}
                  >
                    <span className={`h-2 w-2 rounded-full ${highlightsOn ? 'bg-amber-400' : 'bg-slate-600'}`} />
                    {highlightsOn ? 'Highlights on' : 'Highlights off'}
                  </button>
                )}

                {graphTab === 'pathway' && highlightsOn && (
                  <button
                    onClick={() => { setPpiOn((v) => !v) }}
                    title="Signaling cascade view"
                    className={`flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-medium transition-colors ${
                      ppiOn
                        ? 'bg-indigo-800 text-indigo-200'
                        : 'bg-slate-800 text-slate-400 hover:bg-slate-700 hover:text-slate-200'
                    }`}
                  >
                    <svg className="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
                      <circle cx="6"  cy="12" r="2.5" />
                      <circle cx="18" cy="6"  r="2.5" />
                      <circle cx="18" cy="18" r="2.5" />
                      <line x1="8.5"  y1="11"  x2="15.5" y2="7"  />
                      <line x1="8.5"  y1="13"  x2="15.5" y2="17" />
                    </svg>
                    PPI
                  </button>
                )}

                {graphTab === 'pathway' && highlightsOn && (
                  <button
                    onClick={() => setDrugCarouselOpen((v) => !v)}
                    title="Browse drugs"
                    className={`flex items-center gap-1.5 rounded-md px-2 py-1 text-xs font-medium transition-colors ${
                      drugCarouselOpen
                        ? 'bg-blue-800 text-blue-200'
                        : 'bg-slate-800 text-slate-400 hover:bg-slate-700 hover:text-slate-200'
                    }`}
                  >
                    <svg className="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
                      <path d="M10.5 20.5 3.5 13.5a5 5 0 0 1 7.07-7.07l7 7a5 5 0 0 1-7.07 7.07Z" />
                      <line x1="8.5" y1="8.5" x2="15.5" y2="15.5" />
                    </svg>
                    Drugs
                    {(profileDrugs.length > 0 || allDrugs.length > 0) && (
                      <span className="rounded-full bg-blue-700 px-1.5 py-0.5 text-[9px] font-bold text-blue-100">
                        {profileDrugs.length > 0 ? profileDrugs.length : allDrugs.length}
                      </span>
                    )}
                  </button>
                )}

                <div className="ml-auto flex items-center gap-2" onClick={() => setDrugCarouselOpen(false)}>
                  {urlProfileId && !streamProfileId && (
                    <span className="rounded bg-slate-800 px-2 py-0.5 font-mono text-xs text-slate-400">
                      {urlProfileId}
                    </span>
                  )}
                  <button
                    onClick={handleReset}
                    className="text-xs text-slate-500 hover:text-slate-300 transition-colors"
                  >
                    {urlProfileId && !streamProfileId ? 'Close' : 'New file'}
                  </button>
                  <button
                    onClick={() => setPanelVisible((v) => !v)}
                    className="flex items-center gap-1.5 rounded-md border border-slate-700 px-2.5 py-1 text-xs text-slate-400 hover:border-slate-500 hover:text-slate-200 transition-colors"
                    title={panelVisible ? 'Hide panel' : 'Show panel'}
                  >
                    <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                        d={panelVisible ? 'M9 5l7 7-7 7' : 'M15 19l-7-7 7-7'} />
                    </svg>
                    {panelVisible ? 'Hide panel' : 'Show panel'}
                  </button>
                </div>
              </div>

              {/* Drug carousel dropdown */}
              {drugCarouselOpen && highlightsOn && graphTab === 'pathway' && (
                <DrugCarousel
                  drugs={profileDrugs}
                  loading={drugsLoading}
                  fallbackDrugs={allDrugs as ProfileDrug[]}
                  onSelect={(card) => {
                    setPendingContext(card)
                    setPanelVisible(true)
                  }}
                  onClose={() => setDrugCarouselOpen(false)}
                />
              )}
              </div>

              {graphTab === 'drugs' ? (
                <div className="flex flex-1 overflow-hidden bg-slate-900">
                  <DrugPanel drugs={allDrugs} />
                </div>
              ) : graphTab === 'pathway' ? (
                <PathwayGraph
                  profileId={highlightsOn ? activeProfileId : null}
                  highlights={hydratedList}
                  selectedProtein={selected ? mutations.find((m) => m.mutation_id === selected)?.hydrated?.protein : undefined}
                  ppiView={ppiOn}
                  onDiveDeeper={(card) => {
                    setPendingContext(card)
                    setPanelVisible(true)
                  }}
                  onViewStructure={handleViewStructure}
                />
              ) : (
                <div className="flex flex-1 overflow-hidden bg-slate-900 p-3">
                  {latestSubgraph ? (
                    <SubgraphView
                      subgraph={latestSubgraph.subgraph}
                      fill
                      onNodeClick={(node: SubgraphNode) => {
                        const protein = (node.label || node.symbol || node.id) as string
                        // Try to match to a known mutation for effect, fall back to 'uncertain'
                        const match = hydratedList.find(
                          (m) => m.protein === protein || m.gene === protein,
                        )
                        const card: ContextCard = {
                          id:          node.id,
                          protein,
                          effect:      (match?.estimated_effect as EffectType) ??
                                       (node.estimated_effect as EffectType) ??
                                       'uncertain',
                          mutation_id: match?.mutation_id ?? node.id,
                          pathway:     (node.labels?.[0] === 'Pathway' ? protein : undefined),
                        }
                        setPendingContext(card)
                        setPanelVisible(true)
                      }}
                    />
                  ) : (
                    <p className="m-auto max-w-xs text-center text-sm text-slate-500">
                      Ask the agent a question — its reasoning graph will appear here.
                    </p>
                  )}
                </div>
              )}

            </div>

            {/* ── Right panel ─────────────────────────────────────── */}
            {panelVisible && (
              <AgentPanel
                mutations={mutations}
                selected={selected}
                onSelect={(id) => setSelected(id || null)}
                phase={isHistoryLoad ? 'done' : phase}
                analysisError={visibleError}
                onDismissError={() => setDismissedError(true)}
                filename={filename}
                messages={messages}
                busy={busy}
                onSend={send}
                onStop={stop}
                onRetry={retry}
                pendingContext={pendingContext}
                onClearPendingContext={() => setPendingContext(null)}
                onClearChat={clear}
                onNewSession={newSession}
                profileId={activeProfileId}
                sessions={sessions}
                sessionId={sessionId}
                onSwitchSession={switchSession}
                onMutationPatched={patchMutation}
                onViewStructure={handleViewStructure}
              />
            )}
          </div>
        )}
      </div>

      {structureTarget && (
        <StructureModal
          target={structureTarget}
          onClose={() => setStructureTarget(null)}
        />
      )}
    </div>
  )
}
