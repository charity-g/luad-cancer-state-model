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

  if (phase === 'idle') {
    return (
      <div className="flex h-full flex-col">
        <UploadBox onFile={handleFile} />
      </div>
    )
  }

  return (
    <div className="flex h-full">
      <MutationSidebar
        mutations={mutations}
        selected={selected}
        onSelect={setSelected}
        phase={phase}
        filename={filename}
        onReset={handleReset}
      />

      <div className="flex flex-1 flex-col overflow-hidden border-r border-slate-200">
        <MutationDetail entry={selectedEntry} />
      </div>

      <div className="w-96 flex-shrink-0">
        <PathwayGraph highlights={hydratedList} selectedProtein={selectedProtein} />
      </div>
    </div>
  )
}
