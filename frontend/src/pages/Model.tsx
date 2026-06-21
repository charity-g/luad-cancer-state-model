import { useState } from 'react'
import { useAnalysis } from '../hooks/useAnalysis'
import UploadBox from '../components/UploadBox'
import MutationSidebar from '../components/MutationSidebar'
import MutationDetail from '../components/MutationDetail'
import PathwayGraph from '../components/PathwayGraph'

export default function Model() {
  const { mutations, phase, analyze, reset } = useAnalysis()
  const [selected, setSelected] = useState<string | null>(null)
  const [filename, setFilename] = useState('')

  function handleFile(file: File) {
    setFilename(file.name)
    setSelected(null)
    analyze(file)
  }

  function handleReset() {
    reset()
    setSelected(null)
    setFilename('')
  }

  const selectedEntry = mutations.find((m) => m.mutation_id === selected)
  const hydratedList = mutations.filter((m) => m.hydrated).map((m) => m.hydrated!)
  const selectedProtein = selectedEntry?.hydrated?.protein
  const hasData = phase !== 'idle'
  const [sidebarVisible, setSidebarVisible] = useState(true)
  const [highlightsOn, setHighlightsOn] = useState(true)

  return (
    <div className="flex h-full flex-col">
      {/* Main workspace */}
      <div className="flex flex-1 overflow-hidden">
        {!hasData ? (
          <div className="flex flex-1 flex-col items-center justify-center text-center px-6">
            <svg className="mb-4 h-12 w-12 text-slate-300" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1}
                d="M9 3H5a2 2 0 00-2 2v4m6-6h10a2 2 0 012 2v4M9 3v18m0 0h10a2 2 0 002-2V9M9 21H5a2 2 0 01-2-2V9m0 0h18"
              />
            </svg>
            <h2 className="text-lg font-semibold text-slate-700">Scientific Reasoning Workspace</h2>
            <p className="mt-2 max-w-sm text-sm text-slate-400">
              Upload a mutation CSV below. The agent will identify variants, annotate each with protein
              effects, and visualize affected pathways.
            </p>
          </div>
        ) : (
          <div className="relative flex flex-1 overflow-hidden">
            {sidebarVisible && (
              <MutationSidebar
                mutations={mutations}
                selected={selected}
                onSelect={setSelected}
                phase={phase}
                filename={filename}
                onReset={handleReset}
              />
            )}

            {/* Toggle sidebar button */}
            <button
              onClick={() => setSidebarVisible((v) => !v)}
              className="absolute left-0 top-1/2 z-10 -translate-y-1/2 flex h-8 w-5 items-center justify-center rounded-r-md border border-l-0 border-slate-200 bg-white text-slate-400 shadow-sm hover:bg-slate-50 hover:text-slate-600 transition-all"
              style={{ left: sidebarVisible ? '288px' : '0px' }}
              title={sidebarVisible ? 'Hide mutations' : 'Show mutations'}
            >
              <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d={sidebarVisible ? 'M15 19l-7-7 7-7' : 'M9 5l7 7-7 7'} />
              </svg>
            </button>

            <div className="flex flex-1 flex-col overflow-hidden">
              {/* Graph toolbar */}
              <div className="flex flex-shrink-0 items-center gap-2 border-b border-slate-700 bg-slate-900 px-4 py-2">
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
              </div>
              <PathwayGraph
                highlights={highlightsOn ? hydratedList : []}
                selectedProtein={selectedProtein}
              />
            </div>

            {/* Detail popover — only when a mutation is selected */}
            {selectedEntry && (
              <div className="absolute inset-y-4 right-4 w-80 overflow-hidden rounded-xl border border-slate-200 bg-white shadow-xl flex flex-col">
                <div className="flex items-center justify-between border-b border-slate-100 px-4 py-2.5">
                  <span className="text-xs font-semibold uppercase tracking-widest text-slate-400">
                    Mutation Detail
                  </span>
                  <button
                    onClick={() => setSelected(null)}
                    className="rounded p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600"
                  >
                    <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </button>
                </div>
                <MutationDetail entry={selectedEntry} />
              </div>
            )}
          </div>
        )}
      </div>

      {/* Upload bar — always pinned to bottom */}
      <UploadBox onFile={handleFile} hasData={hasData} filename={filename} />
    </div>
  )
}
