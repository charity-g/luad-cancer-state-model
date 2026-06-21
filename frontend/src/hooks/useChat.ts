import { useState, useCallback } from 'react'
import type { HydratedMutation } from '../types'

export interface ChatMessage {
  id: string
  role: 'user' | 'agent'
  content: string
  streaming?: boolean
}

function uid() {
  return Math.random().toString(36).slice(2)
}

function sleep(ms: number) {
  return new Promise((r) => setTimeout(r, ms))
}

// Generates a contextual response given the current mutation data and a question
function buildResponse(question: string, mutations: HydratedMutation[]): string {
  const q = question.toLowerCase()

  const activating   = mutations.filter((m) => m.estimated_effect === 'activating')
  const inactivating = mutations.filter((m) => m.estimated_effect === 'inactivating')
  const noEffect     = mutations.filter((m) => m.estimated_effect === 'no_effect')

  const pathwayCounts: Record<string, number> = {}
  mutations.forEach((m) => {
    const p = (m.justification['pathway'] as string) ?? 'Unknown'
    pathwayCounts[p] = (pathwayCounts[p] ?? 0) + 1
  })
  const topPathway = Object.entries(pathwayCounts).sort((a, b) => b[1] - a[1])[0]

  const proteinCounts: Record<string, number> = {}
  mutations.forEach((m) => { proteinCounts[m.protein] = (proteinCounts[m.protein] ?? 0) + 1 })
  const topProtein = Object.entries(proteinCounts).sort((a, b) => b[1] - a[1])[0]

  // Detect if user is asking about a specific protein
  const mentionedProtein = mutations.find((m) =>
    q.includes(m.protein.toLowerCase()) || q.includes(m.mutation_id.toLowerCase()),
  )

  if (mutations.length === 0) {
    return 'The analysis has not completed yet. Please wait for all mutations to be annotated before asking questions.'
  }

  if (mentionedProtein) {
    const others = mutations.filter((m) => m.protein === mentionedProtein.protein)
    const ids = others.map((m) => m.mutation_id).join(', ')
    const effect = mentionedProtein.estimated_effect.replace('_', ' ')
    const pathway = mentionedProtein.justification['pathway'] as string
    const mechanism = mentionedProtein.justification['mechanism'] as string
    return (
      `**${mentionedProtein.protein}** is annotated as **${effect}** in this dataset.\n\n` +
      `Affected mutations: ${ids}\n\n` +
      `Pathway: ${pathway}\n\n` +
      `Mechanism: ${mechanism}\n\n` +
      `Frequency in LUAD: ${mentionedProtein.justification['frequency_in_luad'] as string}`
    )
  }

  if (q.includes('how many') || q.includes('count') || q.includes('total')) {
    return (
      `Your dataset contains **${mutations.length} annotated mutation${mutations.length !== 1 ? 's' : ''}**:\n\n` +
      `- Activating: ${activating.length}\n` +
      `- Inactivating: ${inactivating.length}\n` +
      `- No effect: ${noEffect.length}`
    )
  }

  if (q.includes('activating') || q.includes('gain of function') || q.includes('oncogenic')) {
    if (activating.length === 0) return 'No activating mutations were identified in this dataset.'
    const list = activating.map((m) => `**${m.mutation_id}** → ${m.protein}`).join('\n')
    return `**${activating.length} activating mutation${activating.length !== 1 ? 's' : ''}** identified:\n\n${list}`
  }

  if (q.includes('inactivating') || q.includes('loss of function') || q.includes('tumor suppressor')) {
    if (inactivating.length === 0) return 'No inactivating mutations were identified in this dataset.'
    const list = inactivating.map((m) => `**${m.mutation_id}** → ${m.protein}`).join('\n')
    return `**${inactivating.length} inactivating mutation${inactivating.length !== 1 ? 's' : ''}** identified:\n\n${list}`
  }

  if (q.includes('pathway') || q.includes('signaling')) {
    const lines = Object.entries(pathwayCounts)
      .sort((a, b) => b[1] - a[1])
      .map(([p, n]) => `- ${p}: ${n} mutation${n !== 1 ? 's' : ''}`)
      .join('\n')
    return `Pathway distribution across ${mutations.length} mutations:\n\n${lines}`
  }

  if (q.includes('most common') || q.includes('most frequent') || q.includes('dominant')) {
    const resp = []
    if (topProtein) resp.push(`Most affected protein: **${topProtein[0]}** (${topProtein[1]} mutation${topProtein[1] !== 1 ? 's' : ''})`)
    if (topPathway) resp.push(`Most affected pathway: **${topPathway[0]}** (${topPathway[1]} mutation${topPathway[1] !== 1 ? 's' : ''})`)
    return resp.join('\n\n')
  }

  if (q.includes('summary') || q.includes('overview') || q.includes('summarize')) {
    const effectBreakdown = `${activating.length} activating, ${inactivating.length} inactivating, ${noEffect.length} with no predicted effect`
    const proteinList = [...new Set(mutations.map((m) => m.protein))].join(', ')
    return (
      `**Dataset summary**\n\n` +
      `- ${mutations.length} mutations annotated (${effectBreakdown})\n` +
      `- Proteins affected: ${proteinList}\n` +
      (topPathway ? `- Predominant pathway: ${topPathway[0]} (${topPathway[1]} hits)\n` : '') +
      `- Evidence: COSMIC v98 / ClinVar 2024`
    )
  }

  if (q.includes('drug') || q.includes('target') || q.includes('treatment') || q.includes('therapy') || q.includes('inhibitor')) {
    const targetable = activating.filter((m) =>
      ['EGFR', 'KRAS', 'ALK', 'BRAF', 'MET', 'ERBB2', 'RET', 'PIK3CA'].includes(m.protein),
    )
    if (targetable.length === 0) {
      return 'No mutations in well-established targetable oncogenes were detected in this dataset.'
    }
    const list = targetable.map((m) => `**${m.protein}** (${m.mutation_id})`).join(', ')
    return (
      `**${targetable.length} potentially targetable mutation${targetable.length !== 1 ? 's' : ''}** found:\n\n` +
      `${list}\n\n` +
      `These proteins have approved or investigational targeted agents in LUAD. Cross-reference with current NCCN guidelines and clinical trial registries for treatment-eligibility assessment.`
    )
  }

  if (q.includes('confidence') || q.includes('evidence') || q.includes('reliable')) {
    const high = mutations.filter((m) => m.justification['confidence'] === 'high').length
    const med  = mutations.filter((m) => m.justification['confidence'] === 'medium').length
    return (
      `Annotation confidence across ${mutations.length} mutations:\n\n` +
      `- High confidence: ${high}\n` +
      `- Medium confidence: ${med}\n\n` +
      `All annotations are sourced from COSMIC v98 and ClinVar 2024.`
    )
  }

  // Fallback
  return (
    `I can answer questions about this mutation dataset. Try asking:\n\n` +
    `- "How many mutations are activating?"\n` +
    `- "Which pathway is most affected?"\n` +
    `- "Give me a summary"\n` +
    `- "Are there targetable mutations?"\n` +
    `- "Tell me about EGFR"\n\n` +
    `Dataset loaded: **${mutations.length} mutation${mutations.length !== 1 ? 's' : ''}** annotated.`
  )
}

export function useChat(getMutations: () => HydratedMutation[]) {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [busy, setBusy] = useState(false)

  const send = useCallback(async (text: string) => {
    if (!text.trim() || busy) return

    const userMsg: ChatMessage = { id: uid(), role: 'user', content: text.trim() }
    const agentId = uid()
    const agentMsg: ChatMessage = { id: agentId, role: 'agent', content: '', streaming: true }

    setMessages((prev) => [...prev, userMsg, agentMsg])
    setBusy(true)

    await sleep(400)

    const full = buildResponse(text, getMutations())

    // Stream words in
    const words = full.split(' ')
    let accumulated = ''
    for (const word of words) {
      accumulated += (accumulated ? ' ' : '') + word
      const snap = accumulated
      setMessages((prev) =>
        prev.map((m) => (m.id === agentId ? { ...m, content: snap } : m)),
      )
      await sleep(18)
    }

    setMessages((prev) =>
      prev.map((m) => (m.id === agentId ? { ...m, streaming: false } : m)),
    )
    setBusy(false)
  }, [busy, getMutations])

  const clear = useCallback(() => setMessages([]), [])

  return { messages, busy, send, clear }
}
