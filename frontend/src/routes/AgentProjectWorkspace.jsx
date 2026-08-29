import { useCallback, useEffect, useLayoutEffect, useState } from 'react'
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

  const agentFlow = useAgentPhaseFlow(workspaceMode === 'agent')
  // One phase = one agent conversation: `phaseAgent` is reset (fresh create_agent call) every
  // time `agentFlow` advances to a new phase, and drives that phase's own Q&A. `phaseChatAgent`
  // is the separate "Chat with AI" conversation for the current phase, talking to its
  // `<phase>_chat` stage instead of the phase's own. `chatAgent` is the separate freeform
  // "chatbot" conversation opened from manual mode's action bar.
  const phaseAgent = useAgentConversation()
  const phaseChatAgent = useAgentConversation()
  const chatAgent = useAgentConversation()

  // This project defaults to Agent mode every time it's (re-)opened; the slider can flip
  // it to Manual mode from here on, live, for the rest of this visit.
  useLayoutEffect(() => {
    setWorkspaceMode('agent')
    return () => clearWorkspaceMode()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id])

  useEffect(() => {
    const p = getAgentProject(id)
    setProject(p)
    setTitleDraft(p?.project_title ?? '')
    setConversation([])
    setChatOpen(false)
    setPhaseStarted(false)
    setScopeSpecification(null)
    phaseAgent.reset()
    phaseChatAgent.reset()
    chatAgent.reset()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id, getAgentProject])

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

  const appendTurn = useCallback((role, node) => {
    setConversation((prev) => [...prev, { id: crypto.randomUUID(), role, node }])
  }, [])

  // Every phase after scoping (and every phase's chat) gets the finalized scope spec as memory,
  // once one exists.
  const buildPhaseMemory = () => (scopeSpecification ? [scopingMemory(scopeSpecification)] : undefined)

  // Renders one phase agent's response as a transcript turn: its text on "completed"/"error",
  // or just the question text on "awaiting_input" (the interactive answer UI itself lives in
  // `renderAgentBottom`, not the transcript). Also captures the scoping phase's completed turn
  // as the locally stored scope spec, if it parses as one (see `tryParseScope`).
  const appendPhaseResult = (result) => {
    if (!result.ok) {
      appendTurn('assistant', <p className="chat-error-text">{result.error}</p>)
      return
    }
    const { response } = result
    if (agentFlow.phase?.key === 'scoping' && response.status === 'completed') {
      const scope = tryParseScope(response.response)
      if (scope) setScopeSpecification(scope)
    }
    appendTurn('assistant', <p>{response.status === 'awaiting_input' ? response.question.question : response.response}</p>)
  }

  const handleStartPhase = async () => {
    setPhaseStarted(true)
    const result = await phaseAgent.start(
      agentFlow.phase.stage,
      project.description,
      buildPhaseMemory(),
    )
    appendPhaseResult(result)
  }

  // Every phase starts itself automatically - there's no separate "confirm before starting"
  // box, only the continue bar shown once a phase's questions are done.
  useEffect(() => {
    if (workspaceMode === 'agent' && project && agentFlow.phase && !phaseStarted) {
      handleStartPhase()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [workspaceMode, project, agentFlow.phase, phaseStarted])

  const handlePhaseMessage = async (text) => {
    appendTurn('user', <p>{text}</p>)
    appendPhaseResult(await phaseAgent.send(text, buildPhaseMemory()))
  }

  const handleContinuePhase = () => {
    phaseAgent.reset()
    phaseChatAgent.reset()
    setPhaseStarted(false)
    agentFlow.advance()
  }

  const handleManualAction = (key) => {
    if (key === 'chat') {
      setChatOpen(true)
      appendTurn('assistant', <p>You can ask questions about this project below.</p>)
      return
    }
    const labels = {
      summary: 'Generate a summary of the collected papers.',
      gaps: 'Find research gaps across the collected papers.',
      'lit-review': 'Write a full literature review from the collected papers.',
    }
    appendTurn('user', <p>{labels[key]}</p>)
    appendTurn(
      'assistant',
      <PlaceholderNotice
        feature="This action"
        detail="This isn't wired up to the backend yet — and no papers have been collected for this agent project either, since automatic search-term generation isn't implemented."
      />,
    )
  }

  // "Chat with AI" during a phase talks to that phase's dedicated `<phase>_chat` stage, not the
  // phase's own conversation - a fresh, separate conversation from `phaseAgent`. Falls back to
  // the last real phase's chat stage once every phase is done (`agentFlow.phase` is null there).
  // During scoping_chat specifically, a completed turn that parses as a scope spec (the agent
  // applying a requested change) replaces the locally stored one, same as the scoping phase's own
  // completion does.
  const handlePhaseChatMessage = async (text) => {
    appendTurn('user', <p>{text}</p>)
    const chatPhase = agentFlow.phase ?? AGENT_PHASES[AGENT_PHASES.length - 1]
    const memory = buildPhaseMemory()
    const result =
      phaseChatAgent.status === null
        ? await phaseChatAgent.start(chatPhase.chatStage, text, memory)
        : await phaseChatAgent.send(text, memory)

    if (!result.ok) {
      appendTurn('assistant', <p className="chat-error-text">{result.error}</p>)
      return
    }

    const { response } = result
    if (chatPhase.key === 'scoping' && response.status === 'completed') {
      const scope = tryParseScope(response.response)
      if (scope) setScopeSpecification(scope)
    }
    appendTurn('assistant', <p>{response.status === 'awaiting_input' ? response.question.question : response.response}</p>)
  }

  // In manual mode this talks to the standalone "chatbot" agent; in agent mode it's the current
  // phase's dedicated chat conversation.
  const handleChatSend = async (text) => {
    if (workspaceMode === 'agent') return handlePhaseChatMessage(text)

    appendTurn('user', <p>{text}</p>)
    const result =
      chatAgent.status === null ? await chatAgent.start('chatbot', text) : await chatAgent.send(text)
    if (result.ok) {
      appendTurn('assistant', <p>{result.response.response}</p>)
    } else {
      appendTurn('assistant', <p className="chat-error-text">{result.error}</p>)
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
            {turn.node}
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
