import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react'
import { useParams } from 'react-router-dom'
import { useProjects } from '../context/ProjectsContext.jsx'
import { useWorkspaceMode } from '../context/WorkspaceModeContext.jsx'
import { scopingMemory } from '../api/agentClient.js'
import ChatTurn from '../components/chat/ChatTurn.jsx'
import ActionBar from '../components/chat/ActionBar.jsx'
import ChatComposer from '../components/chat/ChatComposer.jsx'
import PlaceholderNotice from '../components/chat/PlaceholderNotice.jsx'
import AgentContinueBar from '../components/chat/AgentContinueBar.jsx'
import AgentQuestion from '../components/chat/AgentQuestion.jsx'
import AgentThoughts from '../components/chat/AgentThoughts.jsx'
import ScopeSummary from '../components/chat/ScopeSummary.jsx'
import { AGENT_PHASES, useAgentPhaseFlow } from '../components/chat/useAgentPhaseFlow.js'
import { useAgentConversation } from '../components/chat/useAgentConversation.js'
import { tryParseScope } from '../components/chat/scopeMemory.js'

export default function AgentProjectWorkspace() {
  const { id } = useParams()
  const { getAgentProject, updateAgentProject } = useProjects()
  const { workspaceMode, setWorkspaceMode, clearWorkspaceMode } = useWorkspaceMode()
  const [project, setProject] = useState(null)
  const [titleDraft, setTitleDraft] = useState('')
  const [editingTitle, setEditingTitle] = useState(false)
  const [conversation, setConversation] = useState([])
  const [chatOpen, setChatOpen] = useState(false)
  const [phaseStarted, setPhaseStarted] = useState(false)
  // The scoping phase's finalized JSON specification (see `scopeMemory.js`) - once set, it's
  // resent as memory to every later phase/chat, and can itself be updated by scoping_chat.
  const [scopeSpecification, setScopeSpecification] = useState(null)

  const agentFlow = useAgentPhaseFlow()
  // One phase = one agent conversation: `phaseAgent` is reset (fresh create_agent call) every
  // time `agentFlow` advances to a new phase, and drives that phase's own Q&A. `phaseChatAgent`
  // is the separate "Chat with AI" conversation for the current phase, talking to its
  // `<phase>_chat` stage instead of the phase's own. `chatAgent` is the separate freeform
  // "chatbot" conversation opened from manual mode's action bar.
  const phaseAgent = useAgentConversation()
  const phaseChatAgent = useAgentConversation()
  const chatAgent = useAgentConversation()

  // Guards the phase auto-start effect below against firing twice for the same phase - a plain
  // `phaseStarted` state check isn't enough because React 18 StrictMode (dev only) invokes effects
  // twice back-to-back before the `setPhaseStarted(true)` from the first invocation has committed,
  // so both invocations would otherwise see `phaseStarted === false` and both would call the agent.
  // A ref is read/written synchronously, so the second invocation always sees the first's write.
  const startedPhaseKeyRef = useRef(null)
  // Whichever phaseAgent call (start or send) most recently failed, so the retry button in
  // `renderAgentBottom` can redo exactly that call instead of restarting the phase from scratch.
  const lastPhaseActionRef = useRef(null)

  // This project defaults to Agent mode every time it's (re-)opened; the slider can flip
  // it to Manual mode from here on, live, for the rest of this visit.
  useLayoutEffect(() => {
    setWorkspaceMode('agent')
    return () => clearWorkspaceMode()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id])

  // Loading a project restores its persisted `agentState` (see the persist effect below) rather
  // than wiping the transcript back to empty - a project that was already mid-conversation stays
  // mid-conversation when reselected. Restoring never issues a request: `hydrate` only sets local
  // state, and `startedPhaseKeyRef` is seeded to match the restored phase whenever it was already
  // started, so the auto-start effect further down sees nothing new to kick off and leaves it
  // alone. Only a project with no persisted state (never opened before) starts blank, which is
  // what lets that effect fire its one legitimate opening call.
  useEffect(() => {
    const p = getAgentProject(id)
    setProject(p)
    setTitleDraft(p?.project_title ?? '')
    lastPhaseActionRef.current = null

    const saved = p?.agentState
    if (saved) {
      setConversation(saved.conversation ?? [])
      setChatOpen(saved.chatOpen ?? false)
      setPhaseStarted(saved.phaseStarted ?? false)
      setScopeSpecification(saved.scopeSpecification ?? null)
      agentFlow.goTo(saved.phaseIndex ?? 0)
      phaseAgent.hydrate(saved.phaseAgent)
      phaseChatAgent.hydrate(saved.phaseChatAgent)
      chatAgent.hydrate(saved.chatAgent)
      startedPhaseKeyRef.current = saved.phaseStarted
        ? (AGENT_PHASES[saved.phaseIndex ?? 0]?.key ?? null)
        : null
    } else {
      setConversation([])
      setChatOpen(false)
      setPhaseStarted(false)
      setScopeSpecification(null)
      agentFlow.goTo(0)
      phaseAgent.reset()
      phaseChatAgent.reset()
      chatAgent.reset()
      startedPhaseKeyRef.current = null
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id, getAgentProject])

  // Mirrors the workspace's full resumable state back to storage after every change, so it's
  // there to restore on the next visit. Reading each agent conversation's snapshot only when its
  // `status`/`question` changed is enough - `applyResponse` (in `useAgentConversation`) always
  // updates its resend history in the same tick, before those, so the snapshot is never stale
  // when this runs.
  useEffect(() => {
    if (!project) return
    updateAgentProject(id, {
      agentState: {
        phaseIndex: agentFlow.phaseIndex,
        phaseStarted,
        scopeSpecification,
        chatOpen,
        conversation,
        phaseAgent: phaseAgent.getSnapshot(),
        phaseChatAgent: phaseChatAgent.getSnapshot(),
        chatAgent: chatAgent.getSnapshot(),
      },
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    id,
    project,
    conversation,
    phaseStarted,
    scopeSpecification,
    chatOpen,
    agentFlow.phaseIndex,
    phaseAgent.status,
    phaseAgent.question,
    phaseChatAgent.status,
    phaseChatAgent.question,
    chatAgent.status,
    chatAgent.question,
  ])

  const commitTitle = async () => {
    setEditingTitle(false)
    const trimmed = titleDraft.trim()
    if (!project || !trimmed || trimmed === project.project_title) {
      setTitleDraft(project?.project_title ?? '')
      return
    }
    const updated = await updateAgentProject(id, { project_title: trimmed })
    setProject(updated)
  }

  // Turns are stored as plain data (kind + payload), not JSX - the transcript is persisted to
  // localStorage (see the persist effect above), and JSX elements don't survive
  // `JSON.stringify`/`JSON.parse`. `renderTurnBody` below turns a stored turn back into markup,
  // for both freshly-appended turns and ones restored from a previous visit.
  const appendTurn = useCallback((role, kind, payload = {}) => {
    setConversation((prev) => [...prev, { id: crypto.randomUUID(), role, kind, payload }])
  }, [])

  // Every phase after scoping (and every phase's chat) gets the finalized scope spec as memory,
  // once one exists.
  const buildPhaseMemory = () => (scopeSpecification ? [scopingMemory(scopeSpecification)] : undefined)

  // Renders one phase agent's *successful* response as a transcript turn: a "Thoughts" disclosure
  // when the turn carried reasoning, then either a friendly scope summary card (when the scoping
  // phase just finalized/updated its specification - see `tryParseScope`) or its plain text. An
  // "awaiting_input" response leaves the transcript untouched - the interactive `AgentQuestion`
  // card in `renderAgentBottom` is the sole representation of a pending question, and
  // `handlePhaseMessage` commits it to history once it's actually answered. Failed calls never
  // reach here - `runPhaseAction` only calls this on `result.ok`, since `renderAgentBottom`'s
  // error+retry block (driven by `phaseAgent.status === 'error'`) covers failures instead.
  const appendPhaseResult = (result) => {
    const { response } = result
    if (response.status === 'awaiting_input') return

    const scope = agentFlow.phase?.key === 'scoping' ? tryParseScope(response.response) : null
    if (scope) setScopeSpecification(scope)

    appendTurn('assistant', 'agent-response', { reasoning: response.reasoning, scope, text: response.response })
  }

  // Runs one phaseAgent call (start or send), remembering it in `lastPhaseActionRef` so a failure
  // can be retried verbatim from `renderAgentBottom` without redoing the transcript writes the
  // caller already made (which would otherwise duplicate turns and re-send the request).
  const runPhaseAction = async (action) => {
    lastPhaseActionRef.current = action
    const result = await action()
    if (result.ok) appendPhaseResult(result)
  }

  // Only the scoping phase should restate the original research description as its opening
  // instruction - later phases (search_review, writing) source their input purely from the
  // scope memory `buildPhaseMemory()` attaches below, so they start with no user instruction at
  // all (`ReactAgent.run_agent` skips adding a user turn for falsy content).
  const handleStartPhase = () => {
    setPhaseStarted(true)
    const content = agentFlow.phase.key === 'scoping' ? project.description : ''
    return runPhaseAction(() => phaseAgent.start(agentFlow.phase.stage, content, buildPhaseMemory()))
  }

  const retryLastPhaseAction = () => {
    if (lastPhaseActionRef.current) runPhaseAction(lastPhaseActionRef.current)
  }

  // Every phase starts itself automatically - there's no separate "confirm before starting"
  // box, only the continue bar shown once a phase's questions are done. Guarded by
  // `startedPhaseKeyRef` (not just `phaseStarted`) so it fires exactly once per phase even under
  // React 18 StrictMode's double effect invocation - see the ref's own comment above.
  useEffect(() => {
    if (
      workspaceMode === 'agent' &&
      project &&
      agentFlow.phase &&
      startedPhaseKeyRef.current !== agentFlow.phase.key
    ) {
      startedPhaseKeyRef.current = agentFlow.phase.key
      handleStartPhase()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [workspaceMode, project, agentFlow.phase])

  // Commits the just-answered question's title to history (the `AgentQuestion` card that showed
  // it has already collapsed by the time this fires - see `AgentQuestion.jsx`), then the user's
  // answer, before continuing the conversation.
  const handlePhaseMessage = (text) => {
    if (phaseAgent.question) {
      appendTurn('assistant', 'text', { text: phaseAgent.question.question })
    }
    appendTurn('user', 'text', { text })
    return runPhaseAction(() => phaseAgent.send(text, buildPhaseMemory()))
  }

  const handleContinuePhase = () => {
    phaseAgent.reset()
    phaseChatAgent.reset()
    setPhaseStarted(false)
    lastPhaseActionRef.current = null
    agentFlow.advance()
  }

  const handleManualAction = (key) => {
    if (key === 'chat') {
      setChatOpen(true)
      appendTurn('assistant', 'text', { text: 'You can ask questions about this project below.' })
      return
    }
    const labels = {
      summary: 'Generate a summary of the collected papers.',
      gaps: 'Find research gaps across the collected papers.',
      'lit-review': 'Write a full literature review from the collected papers.',
    }
    appendTurn('user', 'text', { text: labels[key] })
    appendTurn('assistant', 'placeholder', {
      feature: 'This action',
      detail:
        "This isn't wired up to the backend yet — and no papers have been collected for this agent project either, since automatic search-term generation isn't implemented.",
    })
  }

  // "Chat with AI" during a phase talks to that phase's dedicated `<phase>_chat` stage, not the
  // phase's own conversation - a fresh, separate conversation from `phaseAgent`. Falls back to
  // the last real phase's chat stage once every phase is done (`agentFlow.phase` is null there).
  // During scoping_chat specifically, a completed turn that parses as a scope spec (the agent
  // applying a requested change) replaces the locally stored one, same as the scoping phase's own
  // completion does.
  const handlePhaseChatMessage = async (text) => {
    appendTurn('user', 'text', { text })
    const chatPhase = agentFlow.phase ?? AGENT_PHASES[AGENT_PHASES.length - 1]
    const memory = buildPhaseMemory()
    const result =
      phaseChatAgent.status === null
        ? await phaseChatAgent.start(chatPhase.chatStage, text, memory)
        : await phaseChatAgent.send(text, memory)

    if (!result.ok) {
      appendTurn('assistant', 'error', { text: result.error })
      return
    }

    const { response } = result
    const scope =
      chatPhase.key === 'scoping' && response.status === 'completed'
        ? tryParseScope(response.response)
        : null
    if (scope) setScopeSpecification(scope)

    appendTurn('assistant', 'agent-response', {
      reasoning: response.reasoning,
      scope,
      awaitingQuestion: response.status === 'awaiting_input' ? response.question.question : null,
      text: response.response,
    })
  }

  // In manual mode this talks to the standalone "chatbot" agent; in agent mode it's the current
  // phase's dedicated chat conversation.
  const handleChatSend = async (text) => {
    if (workspaceMode === 'agent') return handlePhaseChatMessage(text)

    appendTurn('user', 'text', { text })
    const result =
      chatAgent.status === null ? await chatAgent.start('chatbot', text) : await chatAgent.send(text)
    if (result.ok) {
      appendTurn('assistant', 'agent-response', {
        reasoning: result.response.reasoning,
        scope: null,
        text: result.response.response,
      })
    } else {
      appendTurn('assistant', 'error', { text: result.error })
    }
  }

  // Turns a stored turn (see `appendTurn`) back into markup - used for both freshly-appended
  // turns and ones restored from a previous visit.
  const renderTurnBody = (turn) => {
    switch (turn.kind) {
      case 'text':
        return <p>{turn.payload.text}</p>
      case 'error':
        return <p className="chat-error-text">{turn.payload.text}</p>
      case 'placeholder':
        return <PlaceholderNotice feature={turn.payload.feature} detail={turn.payload.detail} />
      case 'agent-response': {
        const { reasoning, scope, awaitingQuestion, text } = turn.payload
        return (
          <>
            {reasoning && <AgentThoughts text={reasoning} />}
            {awaitingQuestion ? (
              <p>{awaitingQuestion}</p>
            ) : scope ? (
              <ScopeSummary specification={scope} />
            ) : (
              <p>{text}</p>
            )}
          </>
        )
      }
      default:
        return null
    }
  }

  const renderAgentBottom = () => {
    if (phaseAgent.sending) {
      return (
        <ChatTurn role="assistant" wide>
          <p className="chat-thinking">Thinking…</p>
        </ChatTurn>
      )
    }

    if (agentFlow.done) {
      return (
        <ChatTurn role="assistant" wide>
          <AgentContinueBar showContinue={false} onChat={() => setChatOpen(true)} />
        </ChatTurn>
      )
    }

    if (!phaseStarted) {
      return null
    }

    // A failed start/send leaves no completed response to act on, so this takes priority over the
    // continue bar / question card below - retrying re-issues exactly the call that failed
    // (`retryLastPhaseAction`), instead of the user having to reload the page to try again, which
    // would silently re-run the whole phase from scratch and double up the token spend.
    if (phaseAgent.status === 'error') {
      return (
        <ChatTurn role="assistant" wide>
          <div className="agent-error-block">
            <p className="chat-error-text">Something went wrong reaching the agent. Nothing was sent twice - retry when you're ready.</p>
            <button type="button" className="retry-btn" onClick={retryLastPhaseAction}>
              Retry
            </button>
          </div>
        </ChatTurn>
      )
    }

    if (phaseAgent.question) {
      return (
        <ChatTurn role="assistant" wide>
          <AgentQuestion question={phaseAgent.question} onAnswer={handlePhaseMessage} />
        </ChatTurn>
      )
    }

    return (
      <ChatTurn role="assistant" wide>
        <AgentContinueBar hint={agentFlow.phase.nextHint} onContinue={handleContinuePhase} onChat={() => setChatOpen(true)} />
      </ChatTurn>
    )
  }

  if (!project) return <p className="page-status error">Agent project not found.</p>

  return (
    <div className="workspace">
      <header className="workspace-header">
        {editingTitle ? (
          <input
            className="title-input"
            autoFocus
            value={titleDraft}
            onChange={(e) => setTitleDraft(e.target.value)}
            onBlur={commitTitle}
            onKeyDown={(e) => e.key === 'Enter' && commitTitle()}
          />
        ) : (
          <h1 className="project-title-heading" onClick={() => setEditingTitle(true)} title="Click to rename">
            {project.project_title}
          </h1>
        )}
        <div className="workspace-totals">
          <span className="mode-badge mode-agent">Agent</span>
        </div>
      </header>

      <div className="workspace-thread">
        <ChatTurn role="user">
          <p className="turn-lede">Research description:</p>
          <p>{project.description}</p>
          {project.inclusion_criteria && (
            <>
              <p className="turn-lede">Inclusion / exclusion criteria:</p>
              <p>{project.inclusion_criteria}</p>
            </>
          )}
        </ChatTurn>

        {conversation.map((turn) => (
          <ChatTurn key={turn.id} role={turn.role} wide={turn.role === 'assistant'}>
            {renderTurnBody(turn)}
          </ChatTurn>
        ))}

        {(workspaceMode === 'agent' ? phaseChatAgent.sending : chatAgent.sending) && (
          <ChatTurn role="assistant" wide>
            <p className="chat-thinking">Thinking…</p>
          </ChatTurn>
        )}

        {workspaceMode === 'manual' && (
          <ChatTurn role="assistant" wide>
            <p className="turn-lede">What would you like to do next?</p>
            <ActionBar onAction={handleManualAction} />
          </ChatTurn>
        )}

        {workspaceMode === 'agent' && renderAgentBottom()}
      </div>

      {chatOpen && (
        <ChatComposer
          onSend={handleChatSend}
          disabled={workspaceMode === 'agent' ? phaseAgent.sending || phaseChatAgent.sending : chatAgent.sending}
          placeholder="Ask the agent a question…"
        />
      )}
    </div>
  )
}
