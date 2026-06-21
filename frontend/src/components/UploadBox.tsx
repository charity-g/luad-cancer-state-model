import { useRef, useState } from 'react'
import type { DragEvent, ChangeEvent } from 'react'

interface Props {
  onFile: (file: File) => void
  hasData: boolean
  filename?: string
  standalone?: boolean
}

export default function UploadBox({ onFile, hasData, filename, standalone }: Props) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [dragging, setDragging] = useState(false)

  function handleFile(file: File) {
    if (file.name.endsWith('.csv') || file.type === 'text/csv') {
      onFile(file)
    }
  }

  function onDrop(e: DragEvent) {
    e.preventDefault()
    setDragging(false)
    const file = e.dataTransfer.files[0]
    if (file) handleFile(file)
  }

  function onChange(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (file) handleFile(file)
    e.target.value = ''
  }

  return (
    <div
      className={`flex-shrink-0 bg-white px-4 py-3 transition-colors ${
        standalone
          ? `rounded-2xl border border-slate-200 shadow-lg ${dragging ? 'bg-blue-50' : ''}`
          : `border-t border-slate-200 ${dragging ? 'bg-blue-50' : ''}`
      }`}
      onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
      onDragLeave={() => setDragging(false)}
      onDrop={onDrop}
    >
      <div className="mx-auto flex max-w-3xl items-center gap-3">
        <div
          className={`flex flex-1 cursor-pointer items-center gap-3 rounded-xl border px-4 py-3 transition-colors ${
            dragging
              ? 'border-blue-400 bg-blue-50'
              : 'border-slate-200 bg-slate-50 hover:border-slate-300 hover:bg-slate-100'
          }`}
          onClick={() => inputRef.current?.click()}
        >
          <svg
            className={`h-4 w-4 flex-shrink-0 ${dragging ? 'text-blue-500' : 'text-slate-400'}`}
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
              d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13"
            />
          </svg>
          <span className={`text-sm ${dragging ? 'text-blue-600' : filename ? 'text-slate-600' : 'text-slate-400'}`}>
            {dragging
              ? 'Drop to analyze…'
              : filename
              ? `Loaded: ${filename} — drop a new CSV to re-run`
              : 'Drop a CSV file here, or click to browse'}
          </span>
        </div>

        <button
          onClick={() => inputRef.current?.click()}
          className="flex flex-shrink-0 items-center gap-2 rounded-xl bg-slate-900 px-4 py-3 text-sm font-medium text-white transition-colors hover:bg-slate-700 disabled:opacity-40"
        >
          <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
              d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12"
            />
          </svg>
          {hasData ? 'New file' : 'Upload CSV'}
        </button>

        <input
          ref={inputRef}
          type="file"
          accept=".csv,text/csv"
          className="hidden"
          onChange={onChange}
        />
      </div>

      {!hasData && (
        <p className="mx-auto mt-2 max-w-3xl text-center text-[11px] text-slate-400">
          Expected columns:{' '}
          {['mutation_id', 'gene', 'position', 'ref', 'alt'].map((c, i) => (
            <span key={c}>
              <code className="font-mono">{c}</code>
              {i < 4 ? ', ' : ''}
            </span>
          ))}
        </p>
      )}
    </div>
  )
}
