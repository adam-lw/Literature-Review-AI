import { useCallback, useState } from 'react'
import { createAgent, invokeAgent, paperListMemory, reviewMemory, scopingMemory } from '../../api/agentClient.js'
import { ServerStore } from '../../store/ServerStore.js'
import { STAGE_GROUP } from './useAgentPhaseFlow.js'

const ASK_USER_TOOL = 'ask_user'

// A resend-shaped placeholder for the system entry `_to_response` echoes back on a real
// `invokeAgent` follow-up call - `resume_agent` rebuilds the actual system prompt fresh itself
// (see agent_service/api/routers/invoke_agent.py), so its content is never read, only its
// presence at index 0 (dropped server-side before use).
const PLACEHOLDER_SYSTEM_MESSAGE = { role: 'system', content: '' }

// Builds this turn's `memory` payload by reading the project's current scope/papers/reviews
// straight from Postgres - agent_service holds nothing between calls, so this is "the app"
// (this hook + the backend's plain CRUD reads) reconstructing what a resumed conversation needs
// every time, rather than trusting a locally-cached copy that could drift from what another
// hook instance (e.g. the phase's own agent vs. its "chat with AI" companion) just wrote.
async function loadMemory(projectId, group) {
  const memory = []
  if (group === 'scoping' || group === 'review' || group === 'writing') {
    const scope = await ServerStore.getScope(projectId)
    if (scope) memory.push(scopingMemory(scope.content))
  }
  if (group === 'review' || group === 'writing') {
    const [project, reviews] = await Promise.all([
      ServerStore.getProject(projectId),
      ServerStore.getReviews(projectId),
    ])
    const reviewsByPaper = Object.fromEntries(reviews.map((r) => [r.paper_id, r]))
    const papers = project.searches
      .flatMap((s) => s.results)
      .filter((r) => group !== 'writing' || (reviewsByPaper[r.paper_id]?.included ?? true))
    if (papers.length) {
      memory.push(
        paperListMemory(
          'papers',
          papers.map((p) => ({ paperId: p.paper_id, title: p.title, abstract: p.abstract })),
        ),
      )
    }
    memory.push(
      reviewMemory(
        Object.fromEntries(
          reviews.map((r) => [
            r.paper_id,
            { reviewed: r.reviewed, included: r.included, inclusion_reasoning: r.inclusion_reasoning },
          ]),
        ),
      ),
    )
  }
  return memory
}

// Turns the raw new turns a call produced into what gets persisted - if the turn ended by
// asking the user something, the react loop's last turn is just the flattened "Called tool
// `ask_user` with arguments {...}" bookkeeping text (`response.result` already carries the same
// call structurally, as `response.question`), so that turn is swapped for a proper structured
// entry instead of being persisted as literal chat text. A turn immediately preceding another
// turn from the *same* assistant iteration is always the thinking that led to the call, folded
// in as this entry's content instead of being left as its own turn (it would otherwise render as
// a duplicate, orphaned bubble on reload).
function toPersistedMessages(newMessages, response) {
  const messages = newMessages.map((m) => ({ role: m.role, content: m.content }))
  if (response.status !== 'awaiting_input' || messages.length === 0) return messages

  let thinking = ''
  if (messages.length >= 2 && messages[messages.length - 2].role === 'assistant') {
    thinking = messages.splice(-2, 1)[0].content
  }
  messages[messages.length - 1] = {
    role: 'assistant',
    content: thinking,
    tool_name: ASK_USER_TOOL,
    tool_arguments: { ...response.question },
  }
  return messages
}

// Drives the persisted 3-phase flow's agent calls for one project, against the now fully
// stateless agent_service: every call reloads history/memory fresh from Postgres, resends it in
// full, and persists whatever the response says changed - this hook holds no history/memory of
// its own, so a reload never races an in-flight turn and two hook instances sharing a
// conversation (a phase's own agent and its "chat with AI" companion) never see stale state.
export function usePhaseAgent(projectId) {
  const [sending, setSending] = useState(false)
  const [status, setStatus] = useState(null) // null | 'completed' | 'awaiting_input' | 'error'
  const [question, setQuestion] = useState(null)

  const send = useCallback(
    async (stage, message) => {
      setSending(true)
      try {
        const group = STAGE_GROUP[stage]
        const [conversations, memory] = await Promise.all([
          ServerStore.getConversations(projectId),
          loadMemory(projectId, group),
        ])
        const prior = (conversations[group]?.messages ?? []).map((m) => ({
          role: m.role,
          content: m.content,
        }))

        const response = prior.length
          ? await invokeAgent(stage, [PLACEHOLDER_SYSTEM_MESSAGE, ...prior, { role: 'user', content: message }], memory)
          : await createAgent(stage, message, memory)

        const newMessages = toPersistedMessages(response.messages.slice(1 + prior.length), response)

        const persisting = []
        if (newMessages.length) {
          persisting.push(ServerStore.addConversationMessages(projectId, group, newMessages))
        }
        if (group === 'scoping') {
          const scopeEntry = response.memory.find((m) => m.type === 'scoping')
          if (scopeEntry) persisting.push(ServerStore.setScope(projectId, scopeEntry.specification))
        }
        if (group === 'review') {
          const reviewEntry = response.memory.find((m) => m.type === 'review')
          if (reviewEntry) {
            persisting.push(
              ServerStore.setReviews(
                projectId,
                Object.entries(reviewEntry.reviews).map(([paper_id, r]) => ({ paper_id, ...r })),
              ),
            )
          }
        }
        await Promise.all(persisting)

        setStatus(response.status)
        setQuestion(response.status === 'awaiting_input' ? response.question : null)
        return { ok: true, response }
      } catch (err) {
        setStatus('error')
        return { ok: false, error: err.message }
      } finally {
        setSending(false)
      }
    },
    [projectId],
  )

  const reset = useCallback(() => {
    setStatus(null)
    setQuestion(null)
  }, [])

  // Re-opens a question the agent asked before the page was reloaded, rebuilt from the persisted
  // `ask_user` call (see `reconstructConversation`), so it goes back to being answerable rather
  // than being stranded once this session's own `question` state is gone.
  const restoreQuestion = useCallback((restored) => {
    setStatus('awaiting_input')
    setQuestion(restored)
  }, [])

  return { send, reset, restoreQuestion, sending, status, question }
}
