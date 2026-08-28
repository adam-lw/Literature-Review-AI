import { apiClient } from './client.js'

// Talks to the stateless agent endpoints (literature_ai/core/api/routers/invoke_agent.py). Both
// endpoints keep no memory between calls, so callers must resend the previous response's
// `messages` (plus their new turn) on every follow-up call.
//
// `createAgent` starts a conversation for a given `stage` (a registered agent name, e.g.
// "scoping") from a single opening message. `invokeAgent` continues an already-started
// conversation, resending `stage` too - the backend needs it on every call to resolve the
// agent's settings (llm/tools/allow_questions), not just to pick the initial prompt.
//
// `sessionId` doesn't affect the response - it's forwarded as-is so the backend can group this
// conversation's per-call Langfuse traces into one session in the dashboard.

export async function createAgent(stage, content, paperLists, sessionId) {
  return apiClient.post('/invoke-agent/create', {
    stage,
    content,
    ...(paperLists ? { paper_lists: paperLists } : {}),
    ...(sessionId ? { session_id: sessionId } : {}),
  })
}

export async function invokeAgent(stage, messages, paperLists, sessionId) {
  return apiClient.post('/invoke-agent', {
    stage,
    messages,
    ...(paperLists ? { paper_lists: paperLists } : {}),
    ...(sessionId ? { session_id: sessionId } : {}),
  })
}
