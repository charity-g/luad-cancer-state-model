import { useEffect, useRef, useState } from 'react'
import { useProteinDomains } from '../hooks/useProteinDomains'

// Fixed palette: index 0 is the base grey for undomained regions,
// indices 1-8 are domain colors. Hashed by domain name for consistency.
const DOMAIN_COLORS = [
  '#ef4444', // red
  '#f97316', // orange
  '#eab308', // yellow
  '#22c55e', // green
  '#06b6d4', // cyan
  '#6366f1', // indigo
  '#a855f7', // purple
  '#ec4899', // pink
]

function domainColor(name: string): string {
  let hash = 0
  for (let i = 0; i < name.length; i++) hash = (hash * 31 + name.charCodeAt(i)) >>> 0
  return DOMAIN_COLORS[hash % DOMAIN_COLORS.length]
}

// Extend window type for 3Dmol
declare global {
  interface Window {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    $3Dmol: any
    _3dmolLoading?: boolean
    _3dmolCallbacks?: Array<() => void>
  }
}

function load3Dmol(): Promise<void> {
  if (window.$3Dmol) return Promise.resolve()

  return new Promise((resolve) => {
    if (window._3dmolLoading) {
      window._3dmolCallbacks = window._3dmolCallbacks ?? []
      window._3dmolCallbacks.push(resolve)
      return
    }
    window._3dmolLoading = true
    window._3dmolCallbacks = [resolve]

    const script = document.createElement('script')
    script.src = 'https://3Dmol.org/build/3Dmol-min.js'
    script.async = true
    script.onload = () => {
      window._3dmolCallbacks?.forEach((cb) => cb())
      window._3dmolCallbacks = []
    }
    document.head.appendChild(script)
  })
}

interface Props {
  uniprotAc: string
  mutationResidue: number | null
  heightPx?: number
}

export default function ProteinViewer({ uniprotAc, mutationResidue, heightPx = 260 }: Props) {
  const { data, loading, error } = useProteinDomains(uniprotAc)
  const containerRef = useRef<HTMLDivElement>(null)
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const viewerRef = useRef<any>(null)
  const [structureLoading, setStructureLoading] = useState(false)
  const [structureError, setStructureError] = useState<string | null>(null)

  useEffect(() => {
    if (!data?.pdb_id || !containerRef.current) return

    const pdbId = data.pdb_id
    const chain = data.chain ?? 'A'
    let destroyed = false

    setStructureLoading(true)
    setStructureError(null)

    load3Dmol()
      .then(() => {
        if (destroyed || !containerRef.current) return

        // Clean up any previous viewer
        if (viewerRef.current) {
          try { viewerRef.current.clear() } catch { /* ignore */ }
        }
        containerRef.current.innerHTML = ''

        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const viewer = (window.$3Dmol as any).createViewer(containerRef.current, {
          backgroundColor: 'white',
        })
        viewerRef.current = viewer

        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        window.$3Dmol.download(`pdb:${pdbId.toUpperCase()}`, viewer, {}, () => {
          if (destroyed) return

          // Base style: light grey cartoon
          viewer.setStyle({}, { cartoon: { color: '#cbd5e1' } })

          // Color each domain
          for (const domain of data.domains) {
            const start = domain.pdb_start ?? domain.uniprot_start
            const end   = domain.pdb_end   ?? domain.uniprot_end
            const color = domainColor(domain.name)
            viewer.setStyle(
              { chain, resi: `${start}-${end}` },
              { cartoon: { color } },
            )
          }

          // Pin mutation residue as a sphere
          if (mutationResidue !== null) {
            const domainAtResidue = data.domains.find(
              (d) => mutationResidue >= (d.pdb_start ?? d.uniprot_start) &&
                     mutationResidue <= (d.pdb_end   ?? d.uniprot_end),
            )
            const sphereColor = domainAtResidue ? domainColor(domainAtResidue.name) : '#f43f5e'
            viewer.addSphere({
              center: { resi: mutationResidue, chain },
              radius: 1.5,
              color: sphereColor,
              opacity: 0.9,
            })
            viewer.addLabel(`p.${mutationResidue}`, {
              resi: mutationResidue,
              chain,
              fontSize: 10,
              fontColor: 'white',
              backgroundColor: sphereColor,
              backgroundOpacity: 0.85,
              borderThickness: 0,
            })
          }

          viewer.zoomTo()
          viewer.render()
          setStructureLoading(false)
        })
      })
      .catch((err: unknown) => {
        if (destroyed) return
        setStructureError(err instanceof Error ? err.message : 'Failed to load viewer')
        setStructureLoading(false)
      })

    return () => {
      destroyed = true
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data?.pdb_id, data?.chain, mutationResidue])

  // ── loading / error states ────────────────────────────────────────────────

  if (loading) {
    return (
      <div className="mt-5">
        <SectionLabel />
        <div className="flex h-48 items-center justify-center rounded-xl border border-slate-200 bg-slate-50">
          <div className="flex flex-col items-center gap-2 text-slate-400">
            <div className="h-5 w-5 animate-spin rounded-full border-2 border-slate-200 border-t-blue-500" />
            <p className="text-xs">Fetching domain annotations…</p>
          </div>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="mt-5">
        <SectionLabel />
        <div className="rounded-xl border border-red-100 bg-red-50 px-4 py-3 text-xs text-red-600">
          {error}
        </div>
      </div>
    )
  }

  if (!data) return null

  if (!data.pdb_id) {
    return (
      <div className="mt-5">
        <SectionLabel />
        <div className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-xs text-slate-400">
          No PDB structure found for this protein.
        </div>
      </div>
    )
  }

  if (data.domains.length === 0) {
    return (
      <div className="mt-5">
        <SectionLabel />
        <div className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-xs text-slate-400">
          No annotated domains found in UniProt for {uniprotAc}.
        </div>
      </div>
    )
  }

  return (
    <div className="mt-5">
      <div className="mb-2 flex items-center justify-between">
        <SectionLabel />
        <span className="font-mono text-[10px] text-slate-400 uppercase">{data.pdb_id.toUpperCase()}</span>
      </div>

      {/* 3D viewer */}
      <div className="relative overflow-hidden rounded-xl border border-slate-200">
        <div ref={containerRef} style={{ height: heightPx, width: '100%' }} />
        {structureLoading && (
          <div className="absolute inset-0 flex items-center justify-center bg-white/70">
            <div className="flex flex-col items-center gap-2 text-slate-400">
              <div className="h-5 w-5 animate-spin rounded-full border-2 border-slate-200 border-t-blue-500" />
              <p className="text-xs">Loading structure…</p>
            </div>
          </div>
        )}
        {structureError && (
          <div className="absolute inset-0 flex items-center justify-center bg-white/90">
            <p className="max-w-[200px] text-center text-xs text-red-500">{structureError}</p>
          </div>
        )}
      </div>

      {!data.sifts_available && (
        <p className="mt-1 text-[10px] text-amber-600">
          SIFTS mapping unavailable — domain positions are approximate.
        </p>
      )}

      {/* Domain legend */}
      <div className="mt-3 space-y-1.5">
        {data.domains.map((d) => (
          <div key={d.name} className="flex items-center gap-2">
            <span
              className="h-2.5 w-2.5 flex-shrink-0 rounded-sm"
              style={{ backgroundColor: domainColor(d.name) }}
            />
            <span className="min-w-0 truncate text-xs text-slate-600">{d.name}</span>
            <span className="ml-auto flex-shrink-0 font-mono text-[10px] text-slate-400">
              {d.uniprot_start}–{d.uniprot_end}
            </span>
          </div>
        ))}
        {mutationResidue !== null && (
          <div className="flex items-center gap-2">
            <span className="h-2.5 w-2.5 flex-shrink-0 rounded-full bg-rose-500" />
            <span className="text-xs text-slate-600">Mutation site</span>
            <span className="ml-auto flex-shrink-0 font-mono text-[10px] text-slate-400">
              {mutationResidue}
            </span>
          </div>
        )}
      </div>
    </div>
  )
}

function SectionLabel() {
  return (
    <h3 className="mb-2 text-xs font-semibold uppercase tracking-widest text-slate-400">
      Protein Structure
    </h3>
  )
}
