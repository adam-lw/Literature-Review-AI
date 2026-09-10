import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react'
import { useLocation, useParams } from 'react-router-dom'
import { useProjects } from '../context/ProjectsContext.jsx'
import { useWorkspaceMode } from '../context/WorkspaceModeContext.jsx'
import { generateScopeDescription } from '../api/agentClient.js'
import ChatTurn from '../components/chat/ChatTurn.jsx'
import ActionBar from '../components/chat/ActionBar.jsx'
import ChatComposer from '../components/chat/ChatComposer.jsx'
import PlaceholderNotice from '../components/chat/PlaceholderNotice.jsx'
import AgentContinueBar from '../components/chat/AgentContinueBar.jsx'
import AgentQuestion from '../components/chat/AgentQuestion.jsx'
import AgentThoughts from '../components/chat/AgentThoughts.jsx'
import ScopeSummary from '../components/chat/ScopeSummary.jsx'
import { AGENT_PHASES, STAGE_GROUP, useAgentPhaseFlow } from '../components/chat/useAgentPhaseFlow.js'
import { usePhaseAgent } from '../components/chat/usePhaseAgent.js'
import { useAgentConversation } from '../components/chat/useAgentConversation.js'
import { reconstructConversation } from '../components/chat/reconstructConversation.js'
import { tryParseScope } from '../components/chat/scopeMemory.js'

const GROUP_ORDER = ['scoping', 'review', 'writing']

export default function AgentProjectWorkspace() {
  const { id } = useParams()
  const location = useLocation()
  // Only present the moment we're navigated here right after project creation (see
  // AgentLandingPage.jsx) - not persisted server-side, since it's only ever needed once, as the
  // scoping phase's opening instruction; the message it produces is what actually persists it.
  const initialDescription = location.state?.initialDescription
  const { store, refreshProjects } = useProjects()
  const { workspaceMode, setWorkspaceMode, clearWorkspaceMode } = useWorkspaceMode()
  const [project, setProject] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [titleDraft, setTitleDraft] = useState('')
  const [editingTitle, setEditingTitle] = useState(false)
  const [conversation, setConversation] = useState([])
  const [chatOpen, setChatOpen] = useState(false)
  const [phaseStarted, setPhaseStarted] = useState(false)
  // The scoping phase's finalized JSON specification (see `scopeMemory.js`) - once set, it's
  // resent as memory to every later phase/chat, and can itself be updated by scoping_chat. Now
  // loaded from app.scopes on mount rather than resent by the caller on every call.
  const [scopeSpecification, setScopeSpecification] = useState(null)

  const agentFlow = useAgentPhaseFlow()
  // `phaseAgent` drives the current phase's own auto-progression + question-answering;
  // `phaseChatAgent` is the separate "Chat with AI" conversation for the current phase. Both
  // call the same persisted conversation server-side once their stage/chatStage resolve to the
  // same group (see STAGE_GROUP) - there's no client-held history any more, just per-call UI
  // state (sending/status/question), so nothing here needs snapshotting/hydrating on reload.
  const phaseAgent = usePhaseAgent(id)
  const phaseChatAgent = usePhaseAgent(id)
  // The freeform "chatbot" conversation opened from manual mode's action bar - unaffected by
  // this migration, still the legacy fully-stateless contract. It has no backing store any
  // more (WorkspaceChatStore/AgentLocalStore are gone), so it simply doesn't survive a reload -
  // an accepted, narrow regression for this one freeform side-conversation.
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
  // Guards the initial `load()` effect below against the same StrictMode double-invoke as
  // `startedPhaseKeyRef` above, keyed by project id so navigating to a different project still
  // reloads. Without this, the second concurrent `load()` call resolves after the phase-start
  // effect has already appended the opening user turn and kicked off its agent call, and its
  // `setConversation(restored)` (still reflecting the pre-call, message-less conversation) wipes
  // that turn back out - and resets `startedPhaseKeyRef.current` to null, so the phase-start
  // effect fires *again*, duplicating both the transcript turn and the agent call.
  const loadedIdRef = useRef(null)

  // This project defaults to Agent mode every time it's (re-)opened; the slider can flip
  // it to Manual mode from here on, live, for the rest of this visit.
  useLayoutEffect(() => {
    setWorkspaceMode('agent')
    return () => clearWorkspaceMode()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id])

  // Loads the project plus its persisted conversations/scope from the backend and reconstructs
  // local UI state from them - the transcript, which phase we're on, and whether that phase has
  // already started. Nothing here issues an agent call: reconstructing "already started" (from
  // whether a phase's conversation has any messages) and seeding `startedPhaseKeyRef` to match
  // is what keeps the auto-start effect below from re-issuing an opening call for a phase that's
  // already under way.
  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    lastPhaseActionRef.current = null
    try {
      const [p, conversations, scope] = await Promise.all([
        store.getProject(id),
        store.getConversations(id),
        store.getScope(id),
      ])
      if (!p) {
        setError('Agent project not found.')
        return
      }
      setProject(p)
      setTitleDraft(p.project_title)
      setScopeSpecification(scope?.content ?? null)

      const restored = GROUP_ORDER.map((group) => ({
        group,
        ...reconstructConversation(conversations[group]?.messages ?? [], { isScopingStage: group === 'scoping' }),
      }))
      setConversation(restored.flatMap((r) => r.turns))

      let resumeIndex = AGENT_PHASES.length
      for (let i = 0; i < AGENT_PHASES.length; i++) {
        const group = STAGE_GROUP[AGENT_PHASES[i].stage]
        if (!conversations[group]?.conversation?.completed) {
          resumeIndex = i
          break
        }
      }
      agentFlow.goTo(resumeIndex)

      const currentGroup = resumeIndex < AGENT_PHASES.length ? STAGE_GROUP[AGENT_PHASES[resumeIndex].stage] : null
      const started = currentGroup ? (conversations[currentGroup]?.messages?.length ?? 0) > 0 : false
      setPhaseStarted(started)
      startedPhaseKeyRef.current = started ? (AGENT_PHASES[resumeIndex]?.key ?? null) : null

      setChatOpen(false)
      phaseAgent.reset()
      phaseChatAgent.reset()
      chatAgent.reset()

      // A question the current phase asked but never got an answer to goes back to being a live
      // question card, rather than the phase looking like it simply stopped mid-conversation.
      const pending = restored.find((r) => r.group === currentGroup)?.pendingQuestion
      if (pending) phaseAgent.restoreQuestion(pending)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [store, id])

  useEffect(() => {
    if (loadedIdRef.current === id) return
    loadedIdRef.current = id
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id, load])

  const commitTitle = async () => {
    setEditingTitle(false)
    const trimmed = titleDraft.trim()
    if (!project || !trimmed || trimmed === project.project_title) {
      setTitleDraft(project?.project_title ?? '')
      return
    }
    const updated = await store.updateProject(id, { project_title: trimmed })
    setProject(updated)
    refreshProjects()
  }

  // Turns are stored as plain data (kind + payload), not JSX - `renderTurnBody` below turns a
  // stored turn back into markup, for both freshly-appended turns and ones reconstructed from
  // persisted messages on load (see `reconstructConversation`).
  const appendTurn = useCallback((role, kind, payload = {}) => {
    setConversation((prev) => [...prev, { id: crypto.randomUUID(), role, kind, payload }])
  }, [])

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

  // Runs one phaseAgent call, remembering it in `lastPhaseActionRef` so a failure can be retried
  // verbatim from `renderAgentBottom` without redoing the transcript writes the caller already
  // made (which would otherwise duplicate turns and re-send the request).
  const runPhaseAction = async (action) => {
    lastPhaseActionRef.current = action
    const result = await action()
    if (result.ok) appendPhaseResult(result)
  }

  // Only the scoping phase should restate the original research description as its opening
  // instruction - later phases (search_review, writing) source their input purely from the
  // scope the backend already loaded server-side, so they start with no user instruction at all
  // (`ReactAgent.run_agent` skips adding a user turn for falsy content). A project started from
  // an existing scope has no fresh description at all - its scoping phase is already marked
  // completed server-side, so this branch never fires for it.
  const handleStartPhase = () => {
    setPhaseStarted(true)
    const content = agentFlow.phase.key === 'scoping' ? (initialDescription ?? '') : ''
    if (content) appendTurn('user', 'text', { text: content, lede: 'Research Description:' })
    return runPhaseAction(() => phaseAgent.send(agentFlow.phase.stage, content))
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
    return runPhaseAction(() => phaseAgent.send(agentFlow.phase.stage, text))
  }

  const handleContinuePhase = async () => {
    const group = STAGE_GROUP[agentFlow.phase.stage]
    phaseAgent.reset()
    phaseChatAgent.reset()
    setPhaseStarted(false)
    lastPhaseActionRef.current = null
    if (group === 'scoping' && scopeSpecification) {
      try {
        const { scope_title, scope_description } = await generateScopeDescription(scopeSpecification)
        await store.setScopeMetadata(id, { scope_title, scope_description })
      } catch {
        // Best-effort, like AgentLandingPage's own generateTitle call - the scope's content is
        // already saved regardless; only its title/description would be missing.
      }
    }
    try {
      await store.setConversationCompleted(id, group, true)
    } finally {
      agentFlow.advance()
    }
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
  // phase's own conversation - both persist to the same conversation server-side (see
  // STAGE_GROUP), so this is still a logically separate exchange from `phaseAgent`, just sharing
  // history now instead of each holding its own copy. Falls back to the last real phase's chat
  // stage once every phase is done (`agentFlow.phase` is null there). During scoping_chat
  // specifically, a completed turn that parses as a scope spec (the agent applying a requested
  // change) replaces the locally stored one, same as the scoping phase's own completion does.
  const handlePhaseChatMessage = async (text) => {
    appendTurn('user', 'text', { text })
    const chatPhase = agentFlow.phase ?? AGENT_PHASES[AGENT_PHASES.length - 1]
    const result = await phaseChatAgent.send(chatPhase.chatStage, text)

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
  // turns and ones reconstructed from persisted messages on load.
  const renderTurnBody = (turn) => {
    switch (turn.kind) {
      case 'text':
        return (
          <>
            {turn.payload.lede && <p className="turn-lede">{turn.payload.lede}</p>}
            <p>{turn.payload.text}</p>
          </>
        )
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
            <p className="chat-error-text">Something went wrong reaching the agent. Please try again</p>
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

  if (loading) return <p className="page-status">Loading project…</p>
  if (error) return <p className="page-status error">{error}</p>
  if (!project) return null

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
        {project.inclusion_criteria && (
          <ChatTurn role="user">
            <p className="turn-lede">Inclusion / exclusion criteria:</p>
            <p>{project.inclusion_criteria}</p>
          </ChatTurn>
        )}

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
