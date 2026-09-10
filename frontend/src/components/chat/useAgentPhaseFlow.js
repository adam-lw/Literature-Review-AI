import { useState } from 'react'

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

// Maps every backend `stage` string (both a phase's own stage and its "_chat" companion) onto
// app.conversations' 3-value stage enum (scoping|review|writing) - the two calls for a phase
// share one persisted conversation server-side (see routers/invoke_agent.py's _STAGE_GROUP),
// so this is what the frontend uses to fetch/complete that shared conversation by phase.
export const STAGE_GROUP = {
  scoping: 'scoping',
  scoping_chat: 'scoping',
  search_review: 'review',
  review_chat: 'review',
  writing: 'writing',
  writing_chat: 'writing',
}

// Tracks which of the 3 phases an agent-mode project is on. Bookkeeping only - the phase's
// actual agent conversation lives in a `useAgentConversation` instance the caller drives
// alongside this, restarting it (via `.reset()`) whenever `advance` moves to the next phase.
//
// The caller owns which project this is for - it must call `goTo` explicitly whenever it
// switches projects (0 for a project never started, or the project's persisted phase index to
// resume one already in progress). This hook does not reset itself on its own, so switching
// projects can never silently rewind an in-progress one back to phase 0 and re-trigger its
// opening call.
export function useAgentPhaseFlow() {
  const [phaseIndex, setPhaseIndex] = useState(0)

  return {
    phase: AGENT_PHASES[phaseIndex] ?? null,
    phaseIndex,
    done: phaseIndex >= AGENT_PHASES.length,
    advance: () => setPhaseIndex((i) => i + 1),
    goTo: (index) => setPhaseIndex(index),
  }
}
