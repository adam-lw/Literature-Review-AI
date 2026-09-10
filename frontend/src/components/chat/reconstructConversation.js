import { tryParseScope } from './scopeMemory.js'

const ASK_USER_TOOL = 'ask_user'

// Turns written before tool calls were stored structurally (app.tool_calls) flattened the call
// into the turn's own text. They are bookkeeping, never chat text - recognised here so old
// conversations don't render a raw "Called tool `ask_user` with arguments {...}" bubble.
const LEGACY_TOOL_CALL_TEXT = /^Called tool `/

const isToolCall = (message) =>
  Boolean(message.tool_name) || LEGACY_TOOL_CALL_TEXT.test(message.content)

// Normalizes an `ask_user` call's arguments into the shape `AgentQuestion` renders - the same
// shape the backend builds a live `Question` from (see agent/agent/core/react.py).
const toQuestion = (args) => ({
  question: args?.question ?? '',
  description: args?.description ?? '',
  options: args?.options ?? {},
  allows_freetext: args?.allows_freetext ?? true,
})

// Rebuilds the workspace's transcript turn-list (the shape `appendTurn` produces live, and
// `renderTurnBody` knows how to render) from a stage's persisted messages - used on page load,
// since conversation state now lives in Postgres (app.messages) instead of localStorage.
//
// app.messages logs every turn of every ReAct iteration (see routers/invoke_agent.py), including
// the tool calls the live UI never showed as chat. Messages are split into "runs" at each
// user-role message (a run may have no leading user message at all, e.g. a phase started with an
// empty opening instruction); a run renders as its final plain assistant reply, with the thinking
// that its tool-calling turns carried surfaced as that turn's "Thoughts" panel.
//
// The exception is a run that ended by asking the user something: `ask_user` returns before any
// reply exists, so the run's last turn is the call itself. Answered, it renders the way the live
// flow records an answered question - the question text, followed by the user's reply as the next
// run. Unanswered (nothing follows it at all), it comes back as `pendingQuestion` for the caller
// to re-open as a live question card.
export function reconstructConversation(messages, { isScopingStage = false } = {}) {
  const turns = []
  let pendingQuestion = null
  let i = 0

  const push = (role, kind, payload) => turns.push({ id: crypto.randomUUID(), role, kind, payload })

  while (i < messages.length) {
    let userText = null
    if (messages[i]?.role === 'user') {
      userText = messages[i].content
      i++
    }

    const runStart = i
    while (i < messages.length && messages[i].role !== 'user') i++
    const runMessages = messages.slice(runStart, i)
    const isLastRun = i >= messages.length

    if (userText !== null) push('user', 'text', { text: userText })

    const assistantMessages = runMessages.filter((m) => m.role === 'assistant')
    const toolCalls = assistantMessages.filter(isToolCall)
    const reply = assistantMessages.filter((m) => !isToolCall(m)).pop() ?? null
    const lastCall = toolCalls[toolCalls.length - 1] ?? null

    if (reply) {
      const reasoning = toolCalls.map((m) => m.content).filter(Boolean).join('\n\n') || null
      const scope = isScopingStage ? tryParseScope(reply.content) : null
      push('assistant', 'agent-response', { reasoning, scope, awaitingQuestion: null, text: reply.content })
    } else if (lastCall?.tool_name === ASK_USER_TOOL) {
      const question = toQuestion(lastCall.tool_arguments)
      if (isLastRun) pendingQuestion = question
      else push('assistant', 'text', { text: question.question })
    }
  }

  return { turns, pendingQuestion }
}
