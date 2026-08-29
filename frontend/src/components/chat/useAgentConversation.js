import { useCallback, useRef, useState } from 'react'
import { createAgent, invokeAgent } from '../../api/agentClient.js'

// Drives one agent conversation against the stateless create/invoke split of /invoke-agent. The
// backend keeps no memory between calls, so this hook keeps the last response's `messages` (the
// full react context the backend returned) and resends it, plus the caller's new turn, on every
// follow-up call - `start` calls create_agent (no prior context yet), `send` calls invoke_agent.
//
// One instance is one conversation: the phase flow uses a fresh instance per phase, and the
// freeform "chat with the agent" box uses its own, independent instance.
export function useAgentConversation() {
  const [sending, setSending] = useState(false)
  const [status, setStatus] = useState(null) // null | 'completed' | 'awaiting_input' | 'error'
  const [question, setQuestion] = useState(null)
  const historyRef = useRef(null)
  // Set by `start`, resent by `send` - the backend needs it on every call to resolve the
  // agent's settings (llm/tools/allow_questions), not just to pick the initial prompt.
  const stageRef = useRef(null)
  // One id per hook instance (i.e. per conversation), so every turn reports to the same
  // Langfuse session even though each call is its own request/trace.
  const sessionIdRef = useRef(crypto.randomUUID())

  const applyResponse = (response) => {
    historyRef.current = response.messages
    setStatus(response.status)
    setQuestion(response.status === 'awaiting_input' ? response.question : null)
    return response
  }

  const start = useCallback(async (stage, text, memory) => {
    stageRef.current = stage
    setSending(true)
    try {
      const response = await createAgent(
        stage,
        text,
        memory,
        sessionIdRef.current,
      )
      return { ok: true, response: applyResponse(response) }
    } catch (err) {
      setStatus('error')
      return { ok: false, error: err.message }
    } finally {
      setSending(false)
    }
  }, [])

  const send = useCallback(async (text, memory) => {
    const messages = [...(historyRef.current ?? []), { role: 'user', content: text }]
    setSending(true)
    try {
      const response = await invokeAgent(stageRef.current, messages, memory, sessionIdRef.current)
      return { ok: true, response: applyResponse(response) }
    } catch (err) {
      setStatus('error')
      return { ok: false, error: err.message }
    } finally {
      setSending(false)
    }
  }, [])

  // Starts a brand new conversation on the next `start` call, discarding the resend history.
  const reset = useCallback(() => {
    historyRef.current = null
    setStatus(null)
    setQuestion(null)
    sessionIdRef.current = crypto.randomUUID()
  }, [])

  return { start, send, reset, sending, status, question }
}
