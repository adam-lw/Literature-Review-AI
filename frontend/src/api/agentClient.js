import { apiClient } from './client.js'

// Talks to literature_ai/agent_service/api/routers/invoke_agent.py - a single, fully stateless
// contract used for every stage (scoping/scoping_chat/search_review/review_chat/writing/
// writing_chat, and chatbot/orchestrator outside the phase flow alike). The backend keeps no
// memory between calls: callers must resend the previous response's `messages` (plus their new
// turn) and `memory` on every follow-up call, and read the response's own echoed-back `memory`
// to see what a tool call changed (see `usePhaseAgent.js`/`useAgentConversation.js`).
//
// `memory` is a list of tagged inputs matching the backend's `MemoryInput` discriminated union
// (see `agent_service/api/models.py`) - build entries with `paperListMemory`/`scopingMemory`/
// `reviewMemory` below rather than constructing the `{ type, ... }` shape by hand.
//
// `sessionId` doesn't affect the response - it's forwarded as-is so the backend can group a
// conversation's per-call Langfuse traces into one session in the dashboard.

export function paperListMemory(name, papers) {
  return { type: 'paper_list', name, papers }
}

export function scopingMemory(specification) {
  return { type: 'scoping', specification }
}

export function reviewMemory(reviews) {
  return { type: 'review', reviews }
}

export async function createAgent(stage, content, memory, sessionId) {
  return apiClient.post('/invoke-agent/create', {
    stage,
    content,
    ...(memory?.length ? { memory } : {}),
    ...(sessionId ? { session_id: sessionId } : {}),
  })
}

export async function invokeAgent(stage, messages, memory, sessionId) {
  return apiClient.post('/invoke-agent', {
    stage,
    messages,
    ...(memory?.length ? { memory } : {}),
    ...(sessionId ? { session_id: sessionId } : {}),
  })
}

// Talks to literature_ai/agent_service/api/routers/generate_title.py - generates a working
// title for a new agent project from the user's initial description.
export async function generateTitle(userInput) {
  const { title } = await apiClient.post('/generate-title', { user_input: userInput })
  return title
}

// Talks to literature_ai/agent_service/api/routers/generate_scope_description.py - generates a
// title and description for a finalized scope specification, distinct from the project's own
// project_title/description.
export async function generateScopeDescription(specification) {
  return apiClient.post('/generate-scope-description', { specification })
}
