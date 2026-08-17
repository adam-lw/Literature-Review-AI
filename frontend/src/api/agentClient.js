import { apiClient } from './client.js'

// Talks to the stateless chatbot agent (literature_ai/core/api/routers/invoke_agent.py). The
// endpoint keeps no memory between calls, so callers must resend the full message history —
// and, when relevant, the paper lists referenced by it — every time.
export async function invokeChatAgent(messages, paperLists) {
  const { response } = await apiClient.post('/invoke-agent', {
    messages,
    ...(paperLists ? { paper_lists: paperLists } : {}),
  })
  return response
}
