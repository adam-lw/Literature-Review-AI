import { useEffect, useState } from 'react'

// The 3 stages an agent-mode project moves through, one at a time, each its own agent
// conversation (backend `stage` name) - project scoping, then literature search + inclusion/
// exclusion criteria application, then writing the final review. Separated by the "Continue" bar.
export const AGENT_PHASES = [
  {
    key: 'scoping',
    stage: 'scoping',
    // Backend stage "Chat with AI" talks to during this phase - a separate agent conversation
    // from `stage`, seeded with the scope spec once one exists (see `scopeMemory.js`).
    chatStage: 'scoping_chat',
    label: 'Scoping',
    // Shown in the continue bar once this phase's questions are done, describing what
    // continuing moves on to.
    nextHint: 'Continue to paper discovery, or chat with the AI to further refine your scope first.',
  },
  {
    key: 'search_review',
    stage: 'search_review',
    chatStage: 'review_chat',
    label: 'Search & review',
    nextHint: 'Continue to writing, or chat with the AI to review the search results first.',
  },
  {
    key: 'writing',
    stage: 'writing',
    chatStage: 'writing_chat',
    label: 'Writing',
    nextHint: 'Finish up, or chat with the AI to revise the review first.',
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
