import { useCallback, useEffect, useLayoutEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { useProjects } from '../context/ProjectsContext.jsx'
import { useWorkspaceMode } from '../context/WorkspaceModeContext.jsx'
import ChatTurn from '../components/chat/ChatTurn.jsx'
import ActionBar from '../components/chat/ActionBar.jsx'
import ChatComposer from '../components/chat/ChatComposer.jsx'
import PlaceholderNotice from '../components/chat/PlaceholderNotice.jsx'
import AgentStepPrompt from '../components/chat/AgentStepPrompt.jsx'
import AgentContinueBar from '../components/chat/AgentContinueBar.jsx'
import AgentQuestion from '../components/chat/AgentQuestion.jsx'
import { AGENT_PHASES, useAgentPhaseFlow } from '../components/chat/useAgentPhaseFlow.js'
import { useAgentConversation } from '../components/chat/useAgentConversation.js'

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

  const agentFlow = useAgentPhaseFlow(workspaceMode === 'agent')
  // One phase = one agent conversation: `phaseAgent` is reset (fresh create_agent call) every
  // time `agentFlow` advances to a new phase. `chatAgent` is the separate freeform "chatbot"
  // conversation opened from manual mode's action bar.
  const phaseAgent = useAgentConversation()
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
    phaseAgent.reset()
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

  // Renders one phase agent's response as a transcript turn: its text on "completed"/"error",
  // or just the question text on "awaiting_input" (the interactive answer UI itself lives in
  // `renderAgentBottom`, not the transcript).
  const appendPhaseResult = (result) => {
    if (!result.ok) {
      appendTurn('assistant', <p className="chat-error-text">{result.error}</p>)
      return
    }
    const { response } = result
    appendTurn('assistant', <p>{response.status === 'awaiting_input' ? response.question.question : response.response}</p>)
  }

  const handleStartPhase = async () => {
    setPhaseStarted(true)
    const result = await phaseAgent.start(
      agentFlow.phase.stage,
      project.description,
      undefined,
      project.inclusion_criteria,
    )
    appendPhaseResult(result)
  }

  const handlePhaseMessage = async (text) => {
    appendTurn('user', <p>{text}</p>)
    appendPhaseResult(await phaseAgent.send(text))
  }

  const handleContinuePhase = () => {
    // Keep the last phase's conversation alive once done, so "Chat with AI" from the done
    // state can still discuss its output; every other phase transition starts fresh.
    if (agentFlow.phaseIndex < AGENT_PHASES.length - 1) {
      phaseAgent.reset()
      setPhaseStarted(false)
    }
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

  // In manual mode this talks to the standalone "chatbot" agent; in agent mode it's a follow-up
  // turn in the current phase's own conversation, same as answering a question would be.
  const handleChatSend = async (text) => {
    if (workspaceMode === 'agent') return handlePhaseMessage(text)

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
      return (
        <ChatTurn role="assistant" wide>
          <AgentStepPrompt description={agentFlow.phase.description} onConfirm={handleStartPhase} />
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
        <AgentContinueBar onContinue={handleContinuePhase} onChat={() => setChatOpen(true)} />
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

        {chatAgent.sending && (
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
          disabled={workspaceMode === 'agent' ? phaseAgent.sending : chatAgent.sending}
          placeholder="Ask the agent a question…"
        />
      )}
    </div>
  )
}
