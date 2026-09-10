import { apiClient } from './client.js'

// Talks to literature_ai/agent_service/api/routers/invoke_agent.py. That router has two
// contracts:
//
// - The persisted 3-phase flow (scoping/scoping_chat/search_review/review_chat/writing/
//   writing_chat) - `sendPhaseMessage` below. The backend loads conversation history, scope,
//   and review state from Postgres itself, keyed by `project_id` + `stage` - callers only ever
//   send the new message, never a history/memory payload to resend.
// - The legacy, fully-stateless contract used only by `chatbot`/`orchestrator` (outside the
//   3-phase flow) - `createAgent`/`invokeAgent` below. Both keep no memory between calls, so
//   callers must resend the previous response's `messages` (plus their new turn), and must
//   resend `memory`, on every follow-up call.
//
// `memory` (legacy contract only) is a list of tagged inputs matching the backend's
// `MemoryInput` discriminated union (see `agent_service/api/models.py`) - build entries with
// `paperListMemory`/`scopingMemory` below rather than constructing the `{ type, ... }` shape by
// hand.
//
// `sessionId` doesn't affect the response - it's forwarded as-is so the backend can group a
// conversation's per-call Langfuse traces into one session in the dashboard.

export async function sendPhaseMessage(projectId, stage, message, sessionId) {
  return apiClient.post('/invoke-agent', {
    stage,
    project_id: projectId,
    message,
    ...(sessionId ? { session_id: sessionId } : {}),
  })
}

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
