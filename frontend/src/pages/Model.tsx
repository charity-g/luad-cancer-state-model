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
            <MutationSidebar
              mutations={mutations}
              selected={selected}
              onSelect={setSelected}
              phase={phase}
              filename={filename}
              onReset={handleReset}
            />
            <div className="flex flex-1 overflow-hidden">
              <PathwayGraph highlights={hydratedList} selectedProtein={selectedProtein} />
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
