import { useState, useCallback } from 'react'
import type { MutationEntry, HydratedMutation, EffectType } from '../types'

// Mock LUAD protein database — stands in for backend enrichment
const LUAD_PROTEINS: Array<{
  protein: string
  estimated_effect: EffectType
  pathway: string
  mechanism: string
  frequency: string
}> = [
  {
    protein: 'EGFR',
    estimated_effect: 'activating',
    pathway: 'RTK/MAPK',
    mechanism: 'Kinase domain gain-of-function',
    frequency: '~15% LUAD',
  },
  {
    protein: 'KRAS',
    estimated_effect: 'activating',
    pathway: 'RAS/MAPK',
    mechanism: 'GTPase activity loss, constitutive RAS-GTP',
    frequency: '~30% LUAD',
  },
  {
    protein: 'TP53',
    estimated_effect: 'inactivating',
    pathway: 'Cell Cycle / Apoptosis',
    mechanism: 'Loss of transcriptional tumor suppressor activity',
    frequency: '~50% LUAD',
  },
  {
    protein: 'BRAF',
    estimated_effect: 'activating',
    pathway: 'MAPK',
    mechanism: 'Serine/threonine kinase hyperactivation',
    frequency: '~5–7% LUAD',
  },
  {
    protein: 'ALK',
    estimated_effect: 'activating',
    pathway: 'RTK/MAPK',
    mechanism: 'Fusion-driven kinase activation',
    frequency: '~5% LUAD',
  },
  {
    protein: 'MET',
    estimated_effect: 'activating',
    pathway: 'RTK/MAPK',
    mechanism: 'Exon 14 skipping or amplification',
    frequency: '~3–5% LUAD',
  },
  {
    protein: 'STK11',
    estimated_effect: 'inactivating',
    pathway: 'AMPK/mTOR',
    mechanism: 'Loss of AMPK activation, unrestrained mTOR',
    frequency: '~20% LUAD',
  },
  {
    protein: 'KEAP1',
    estimated_effect: 'inactivating',
    pathway: 'NRF2/Oxidative stress',
    mechanism: 'Loss of NRF2 ubiquitination, constitutive NRF2',
    frequency: '~20% LUAD',
  },
  {
    protein: 'PIK3CA',
    estimated_effect: 'activating',
    pathway: 'PI3K/AKT/mTOR',
    mechanism: 'Catalytic subunit gain-of-function',
    frequency: '~7% LUAD',
  },
  {
    protein: 'PTEN',
    estimated_effect: 'inactivating',
    pathway: 'PI3K/AKT/mTOR',
    mechanism: 'Loss of PIP3 phosphatase activity',
    frequency: '~5% LUAD',
  },
  {
    protein: 'RB1',
    estimated_effect: 'inactivating',
    pathway: 'Cell Cycle',
    mechanism: 'Loss of G1/S checkpoint control',
    frequency: '~4% LUAD',
  },
  {
    protein: 'ERBB2',
    estimated_effect: 'activating',
    pathway: 'RTK/MAPK',
    mechanism: 'Exon 20 insertion or amplification',
    frequency: '~3% LUAD',
  },
]

function hashString(s: string): number {
  let h = 0
  for (let i = 0; i < s.length; i++) {
    h = (Math.imul(31, h) + s.charCodeAt(i)) | 0
  }
  return Math.abs(h)
}

function pickProtein(mutation_id: string) {
  return LUAD_PROTEINS[hashString(mutation_id) % LUAD_PROTEINS.length]
}

function sleep(ms: number) {
  return new Promise((r) => setTimeout(r, ms))
}

function parseCSVMutationIds(text: string): string[] {
  const lines = text.trim().split(/\r?\n/)
  if (lines.length === 0) return []

  const header = lines[0].toLowerCase().split(',')
  const colIndex = header.findIndex((h) =>
    ['mutation_id', 'mutation', 'variant_id', 'variant', 'id'].includes(h.trim()),
  )
  const idx = colIndex >= 0 ? colIndex : 0

  return lines
    .slice(1)
    .map((l) => l.split(',')[idx]?.trim())
    .filter(Boolean) as string[]
}

export function useAnalysis() {
  const [mutations, setMutations] = useState<MutationEntry[]>([])
  const [phase, setPhase] = useState<'idle' | 'streaming' | 'done'>('idle')

  const analyze = useCallback(async (file: File) => {
    setMutations([])
    setPhase('streaming')

    const text = await file.text()
    const ids = parseCSVMutationIds(text)

    // Stream 1: emit identified mutation IDs
    for (const mutation_id of ids) {
      await sleep(200)
      setMutations((prev) => [...prev, { mutation_id, status: 'identified' }])
    }

    // Stream 2: hydrate each mutation sequentially
    for (const mutation_id of ids) {
      await sleep(120)
      setMutations((prev) =>
        prev.map((m) => (m.mutation_id === mutation_id ? { ...m, status: 'hydrating' } : m)),
      )

      await sleep(480)
      const meta = pickProtein(mutation_id)
      const hydrated: HydratedMutation = {
        mutation_id,
        protein: meta.protein,
        estimated_effect: meta.estimated_effect,
        justification: {
          pathway: meta.pathway,
          mechanism: meta.mechanism,
          frequency_in_luad: meta.frequency,
          evidence_source: 'COSMIC v98 / ClinVar 2024',
          confidence: hashString(mutation_id) % 3 === 0 ? 'high' : 'medium',
        },
      }
      setMutations((prev) =>
        prev.map((m) => (m.mutation_id === mutation_id ? { ...m, status: 'done', hydrated } : m)),
      )
    }

    setPhase('done')
  }, [])

  const reset = useCallback(() => {
    setMutations([])
    setPhase('idle')
  }, [])

  return { mutations, phase, analyze, reset }
}
