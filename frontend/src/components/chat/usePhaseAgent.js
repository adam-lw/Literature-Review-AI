import { useCallback, useState } from 'react'
import { sendPhaseMessage } from '../../api/agentClient.js'
import { ServerStore } from '../../store/ServerStore.js'
import { STAGE_GROUP } from './useAgentPhaseFlow.js'

// Drives the persisted 3-phase flow's agent calls for one project. Unlike `useAgentConversation`
// (still used for the freeform chatbot, which keeps the old fully-stateless contract), this hook
// holds no history/memory of its own - the backend loads its context from Postgres, keyed by
// project id + stage, so there's nothing here to snapshot/hydrate/reset across a reload.
// `status`/`question` are purely this-session UI state (spinner/question-card), not something
// that needs to survive a reload - see the caller's transcript-reconstruction logic for that.
export function usePhaseAgent(projectId) {
  const [sending, setSending] = useState(false)
  const [status, setStatus] = useState(null) // null | 'completed' | 'awaiting_input' | 'error'
  const [question, setQuestion] = useState(null)

  const send = useCallback(
    async (stage, message) => {
      setSending(true)
      try {
        const response = await sendPhaseMessage(projectId, stage, message)

        // agent_service persists nothing itself (see invoke_agent.py) - it hands back what this
        // turn produced, and this is what actually writes it to Postgres. Awaited before `send`
        // resolves so the next call always reads a consistent state, and a reload never races
        // an in-flight turn; a failure here surfaces as this call failing, same as an agent
        // error, since an unpersisted turn isn't durably done from the UI's perspective either.
        const group = STAGE_GROUP[stage]
        await Promise.all([
          response.new_messages?.length
            ? ServerStore.addConversationMessages(projectId, group, response.new_messages)
            : null,
          response.scope ? ServerStore.setScope(projectId, response.scope) : null,
          response.reviews ? ServerStore.setReviews(projectId, response.reviews) : null,
        ])

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
