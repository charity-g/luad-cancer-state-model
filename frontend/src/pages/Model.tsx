import { useState, useCallback } from 'react'
import { useAnalysis } from '../hooks/useAnalysis'
import { useChat } from '../hooks/useChat'
import UploadBox from '../components/UploadBox'
import AgentPanel from '../components/AgentPanel'
import PathwayGraph from '../components/PathwayGraph'
import type { HydratedMutation, ContextCard } from '../types'

export default function Model() {
  const { mutations, phase, error: analysisError, analyze, reset } = useAnalysis()
  const [selected, setSelected] = useState<string | null>(null)
  const [filename, setFilename] = useState('')
  const [panelVisible, setPanelVisible] = useState(true)
  const [highlightsOn, setHighlightsOn] = useState(true)
  const [pendingContext, setPendingContext] = useState<ContextCard | null>(null)

  const getHydrated = useCallback(
    (): HydratedMutation[] => mutations.filter((m) => m.hydrated).map((m) => m.hydrated!),
    [mutations],
  )
  const { messages, busy, send, clear } = useChat(getHydrated)

  function handleFile(file: File) {
    setFilename(file.name)
    setSelected(null)
    analyze(file)
    setPanelVisible(true)
  }

  function handleReset() {
    reset()
    setSelected(null)
    setFilename('')
    setPendingContext(null)
    clear()
  }

  const hydratedList = mutations.filter((m) => m.hydrated).map((m) => m.hydrated!)
  const hasData = phase !== 'idle'
  const [dismissedError, setDismissedError] = useState(false)
  const visibleError = dismissedError ? null : analysisError

  return (
    <div className="flex h-full flex-col">
      {/* ── Main workspace ──────────────────────────────────────── */}
      <div className="flex flex-1 overflow-hidden">
        {!hasData ? (
          // idle splash
          <div className="flex flex-1 flex-col items-center justify-center px-6 text-center">
            <svg className="mb-4 h-12 w-12 text-slate-300" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1}
                d="M9 3H5a2 2 0 00-2 2v4m6-6h10a2 2 0 012 2v4M9 3v18m0 0h10a2 2 0 002-2V9M9 21H5a2 2 0 01-2-2V9m0 0h18" />
            </svg>
            <h2 className="text-lg font-semibold text-slate-700">Scientific Reasoning Workspace</h2>
            <p className="mt-2 max-w-sm text-sm text-slate-400">
              Upload a mutation CSV below. The agent will identify variants, annotate each with protein
              effects, and visualize affected pathways.
            </p>
          </div>
        ) : (
          // active workspace: graph (center) + agent panel (right)
          <div className="flex flex-1 overflow-hidden">
            {/* ── Graph area ─────────────────────────────────────── */}
            <div className="flex flex-1 flex-col overflow-hidden">
              {/* toolbar */}
              <div className="flex flex-shrink-0 items-center gap-3 border-b border-slate-700 bg-slate-900 px-4 py-2">
                <button
                  onClick={() => setHighlightsOn((v) => !v)}
                  className={`flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-medium transition-colors ${
                    highlightsOn
                      ? 'bg-slate-700 text-slate-200 hover:bg-slate-600'
                      : 'bg-slate-800 text-slate-500 hover:bg-slate-700 hover:text-slate-300'
                  }`}
                >
                  <span className={`h-2 w-2 rounded-full ${highlightsOn ? 'bg-amber-400' : 'bg-slate-600'}`} />
                  {highlightsOn ? 'Highlights on' : 'Highlights off'}
                </button>

                <div className="ml-auto flex items-center gap-2">
                  <button
                    onClick={handleReset}
                    className="text-xs text-slate-500 hover:text-slate-300 transition-colors"
                  >
                    New file
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

              <PathwayGraph
                highlights={highlightsOn ? hydratedList : []}
                selectedProtein={selected ? mutations.find((m) => m.mutation_id === selected)?.hydrated?.protein : undefined}
                onDiveDeeper={(card) => {
                  setPendingContext(card)
                  setPanelVisible(true)
                }}
              />
            </div>

            {/* ── Right panel ─────────────────────────────────────── */}
            {panelVisible && (
              <AgentPanel
                mutations={mutations}
                selected={selected}
                onSelect={setSelected}
                phase={phase}
                filename={filename}
                messages={messages}
                busy={busy}
                onSend={send}
                pendingContext={pendingContext}
                onClearPendingContext={() => setPendingContext(null)}
              />
            )}
          </div>
        )}
      </div>

      {/* ── Upload bar (idle only) ───────────────────────────────── */}
      {!hasData && <UploadBox onFile={handleFile} hasData={false} />}
    </div>
  )
}
