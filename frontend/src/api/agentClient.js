import { apiClient } from './client.js'

// Talks to the stateless agent endpoints (literature_ai/agent_service/api/routers/invoke_agent.py).
// Both endpoints keep no memory between calls, so callers must resend the previous response's
// `messages` (plus their new turn), and must resend `memory`, on every follow-up call.
//
// `createAgent` starts a conversation for a given `stage` (a registered agent name, e.g.
// "scoping") from a single opening message. `invokeAgent` continues an already-started
// conversation, resending `stage` too - the backend needs it on every call to resolve the
// agent's settings (llm/tools/allow_questions), not just to pick the initial prompt.
//
// `memory` is a list of tagged inputs matching the backend's `MemoryInput` discriminated union
// (see `agent_service/api/models.py`) - build entries with `paperListMemory`/`scopingMemory`
// below rather than constructing the `{ type, ... }` shape by hand.
//
// `sessionId` doesn't affect the response - it's forwarded as-is so the backend can group this
// conversation's per-call Langfuse traces into one session in the dashboard.

export function paperListMemory(name, papers) {
  return { type: 'paper_list', name, papers }
}

export function scopingMemory(specification) {
  return { type: 'scoping', specification }
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
