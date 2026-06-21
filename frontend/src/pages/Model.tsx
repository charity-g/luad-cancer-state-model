import { useState, useCallback, useMemo, useEffect, useRef } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useAnalysis } from '../hooks/useAnalysis'
import { useProfileGraph } from '../hooks/useProfileGraph'
import { useChat } from '../hooks/useChat'
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
          // idle splash
          <div className="flex flex-1 flex-col items-center justify-center gap-6 px-6">
            <div className="text-center">
              <svg className="mx-auto mb-4 h-12 w-12 text-slate-300" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1}
                  d="M9 3H5a2 2 0 00-2 2v4m6-6h10a2 2 0 012 2v4M9 3v18m0 0h10a2 2 0 002-2V9M9 21H5a2 2 0 01-2-2V9m0 0h18" />
              </svg>
              <h2 className="text-lg font-semibold text-slate-700">Scientific Reasoning Workspace</h2>
              <p className="mt-2 max-w-sm text-sm text-slate-700">
                Upload a mutation profile CSV to identify variants, annotate protein effects, and visualize affected pathways.
              </p>
            </div>
            <div className="w-full max-w-md">
              <UploadBox onFile={handleFile} hasData={false} standalone />
            </div>
          </div>
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
