import { useCallback, useRef, useState } from 'react'
import { invokeChatAgent } from '../../api/agentClient.js'

// Drives the chat composer against the stateless /invoke-agent endpoint. The endpoint keeps no
// server-side memory, so this hook keeps the running message history on the client and resends
// it, in full, with every send.
export function useChatAgent() {
  const [sending, setSending] = useState(false)
  const historyRef = useRef([])

  const sendMessage = useCallback(async (text, paperLists) => {
    historyRef.current = [...historyRef.current, { role: 'user', content: text }]
    setSending(true)
    try {
      const response = await invokeChatAgent(historyRef.current, paperLists)
      historyRef.current = [...historyRef.current, { role: 'assistant', content: response }]
      return { ok: true, response }
    } catch (err) {
      // Drop the failed turn from history so a retry resends a clean sequence.
      historyRef.current = historyRef.current.slice(0, -1)
      return { ok: false, error: err.message }
    } finally {
      setSending(false)
    }
  }, [])

  return { sendMessage, sending }
}
