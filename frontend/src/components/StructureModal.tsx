import { useEffect } from 'react'
import { createPortal } from 'react-dom'
import ProteinViewer from './ProteinViewer'

export interface StructureTarget {
  uniprotAc: string
  proteinName: string
  mutationResidue: number | null
}

interface Props {
  target: StructureTarget
  onClose: () => void
}

export default function StructureModal({ target, onClose }: Props) {
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  return createPortal(
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-6 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="flex max-h-[90vh] w-full max-w-3xl flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex flex-shrink-0 items-center gap-3 border-b border-slate-100 px-6 py-4">
          <div className="flex h-9 w-9 items-center justify-center rounded-full bg-blue-50">
            <svg className="h-4 w-4 text-blue-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z" />
            </svg>
          </div>
          <div className="min-w-0">
            <p className="font-semibold text-slate-800">{target.proteinName}</p>
            <p className="font-mono text-xs text-slate-400">{target.uniprotAc}</p>
          </div>
          {target.mutationResidue !== null && (
            <span className="ml-2 rounded-full border border-rose-200 bg-rose-50 px-2.5 py-0.5 text-xs font-semibold text-rose-700">
              residue {target.mutationResidue}
            </span>
          )}
          <button
            onClick={onClose}
            className="ml-auto flex-shrink-0 rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-600"
            title="Close (Esc)"
          >
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Body — scrollable, viewer fills it */}
        <div className="flex-1 overflow-y-auto px-6 pb-6">
          <ProteinViewer
            uniprotAc={target.uniprotAc}
            mutationResidue={target.mutationResidue}
            heightPx={480}
          />
        </div>
      </div>
    </div>,
    document.body,
  )
}
