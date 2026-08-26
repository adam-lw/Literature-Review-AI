import { useEffect, useState } from 'react'

// The 3 stages an agent-mode project moves through, one at a time, each its own agent
// conversation (backend `stage` name) - project scoping, then literature search + inclusion/
// exclusion criteria application, then writing the final review. Separated by the "Continue" bar.
export const AGENT_PHASES = [
  {
    key: 'scoping',
    stage: 'scoping',
    label: 'Scoping',
    description: 'Define the scope of this literature review.',
  },
  {
    key: 'search_review',
    stage: 'search_review',
    label: 'Search & review',
    description: 'Search the literature and evaluate candidate papers against the inclusion/exclusion criteria.',
  },
  {
    key: 'writing',
    stage: 'writing',
    label: 'Writing',
    description: 'Write the full literature review.',
  },
]

// Tracks which of the 3 phases an agent-mode project is on. Bookkeeping only - the phase's
// actual agent conversation lives in a `useAgentConversation` instance the caller drives
// alongside this, restarting it (via `.reset()`) whenever `advance` moves to the next phase.
export function useAgentPhaseFlow(active) {
  const [phaseIndex, setPhaseIndex] = useState(0)

  // Every time this project (re-)enters Agent mode, start from the first phase.
  useEffect(() => {
    if (active) setPhaseIndex(0)
  }, [active])

  return {
    phase: AGENT_PHASES[phaseIndex] ?? null,
    phaseIndex,
    done: phaseIndex >= AGENT_PHASES.length,
    advance: () => setPhaseIndex((i) => i + 1),
  }
}
