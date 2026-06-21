import { useRef, useState, DragEvent, ChangeEvent } from 'react'

interface Props {
  onFile: (file: File) => void
}

export default function UploadBox({ onFile }: Props) {
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
  }

  return (
    <div className="flex flex-1 flex-col items-center justify-center px-6 py-16">
      <div className="w-full max-w-xl">
        <div className="mb-6 text-center">
          <div className="mb-3 flex justify-center">
            <svg
              className="h-10 w-10 text-slate-400"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={1.5}
                d="M9 3H5a2 2 0 00-2 2v4m6-6h10a2 2 0 012 2v4M9 3v18m0 0h10a2 2 0 002-2V9M9 21H5a2 2 0 01-2-2V9m0 0h18"
              />
            </svg>
          </div>
          <h2 className="text-xl font-semibold text-slate-800">Upload mutation data</h2>
          <p className="mt-1 text-sm text-slate-500">
            CSV with a <code className="rounded bg-slate-100 px-1 py-0.5 font-mono text-xs">mutation_id</code> column.
            The analysis agent will identify and annotate each variant.
          </p>
        </div>

        <div
          onClick={() => inputRef.current?.click()}
          onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
          className={`cursor-pointer rounded-xl border-2 border-dashed px-8 py-10 text-center transition-colors ${
            dragging
              ? 'border-blue-400 bg-blue-50'
              : 'border-slate-300 bg-white hover:border-slate-400 hover:bg-slate-50'
          }`}
        >
          <svg
            className={`mx-auto mb-3 h-8 w-8 ${dragging ? 'text-blue-400' : 'text-slate-400'}`}
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={1.5}
              d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12"
            />
          </svg>
          <p className="text-sm font-medium text-slate-600">
            {dragging ? 'Drop to begin analysis' : 'Drop CSV here or click to browse'}
          </p>
          <p className="mt-1 text-xs text-slate-400">Only .csv files are accepted</p>
          <input
            ref={inputRef}
            type="file"
            accept=".csv,text/csv"
            className="hidden"
            onChange={onChange}
          />
        </div>

        <div className="mt-4 rounded-lg bg-slate-50 px-4 py-3">
          <p className="mb-1 text-xs font-medium text-slate-500 uppercase tracking-wide">Expected columns</p>
          <div className="flex flex-wrap gap-2">
            {['mutation_id', 'gene', 'position', 'ref', 'alt'].map((col) => (
              <span
                key={col}
                className="rounded bg-white px-2 py-0.5 font-mono text-xs text-slate-600 border border-slate-200"
              >
                {col}
              </span>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
