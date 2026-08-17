import { useCallback, useEffect, useLayoutEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { useProjects } from '../context/ProjectsContext.jsx'
import { useWorkspaceMode } from '../context/WorkspaceModeContext.jsx'
import ResultsPanel from '../components/ResultsPanel.jsx'
import ChatTurn from '../components/chat/ChatTurn.jsx'
import ActionBar from '../components/chat/ActionBar.jsx'
import ChatComposer from '../components/chat/ChatComposer.jsx'
import FormatQuestionnaire from '../components/chat/FormatQuestionnaire.jsx'
import PlaceholderNotice from '../components/chat/PlaceholderNotice.jsx'
import AgentStepPrompt from '../components/chat/AgentStepPrompt.jsx'
import AgentContinueBar from '../components/chat/AgentContinueBar.jsx'
import { useAgentStepFlow } from '../components/chat/useAgentStepFlow.js'
import { useChatAgent } from '../components/chat/useChatAgent.js'

export default function AgentProjectWorkspace() {
  const { id } = useParams()
  const { getAgentProject, updateAgentProject } = useProjects()
  const { workspaceMode, setWorkspaceMode, clearWorkspaceMode } = useWorkspaceMode()
  const [project, setProject] = useState(null)
  const [titleDraft, setTitleDraft] = useState('')
  const [editingTitle, setEditingTitle] = useState(false)
  const [conversation, setConversation] = useState([])
  const [chatOpen, setChatOpen] = useState(false)
  const [formatPrefs, setFormatPrefs] = useState(null)

  const agentFlow = useAgentStepFlow(workspaceMode === 'agent')
  const chatAgent = useChatAgent()

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
    setFormatPrefs(null)
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

  const handleAgentStepConfirm = () => {
    const { step } = agentFlow
    if (step.kind === 'notice') {
      const detail =
        step.key === 'writing' && formatPrefs
          ? `The writing agent will draft a review formatted in ${formatPrefs.citationStyle} style, covering: ${formatPrefs.sections.join(', ')}, once paper collection and evaluation are implemented.`
          : step.detail
      appendTurn('assistant', <PlaceholderNotice feature={step.feature} detail={detail} />)
    } else if (step.kind === 'evaluate') {
      appendTurn(
        'assistant',
        <div>
          <p className="turn-lede">Agent evaluation</p>
          <ResultsPanel
            searches={[]}
            dedupeCounts={{}}
            onToggleInclude={() => {}}
            onSetAll={() => {}}
            onRemoveTerm={() => {}}
            emptyTitle="No papers collected yet"
            emptyDescription="Once paper collection is implemented, results will appear here grouped by generated search term — each with a brief agent summary and an inclusion/exclusion verdict against your criteria in the expanded view."
          />
        </div>,
      )
    }
    agentFlow.confirm()
  }

  const handleAgentFormatSubmit = ({ citationStyle, sections }) => {
    setFormatPrefs({ citationStyle, sections })
    appendTurn(
      'user',
      <p>
        {citationStyle} format, sections: {sections.join(', ')}.
      </p>,
    )
    agentFlow.confirm()
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

  const handleChatSend = async (text) => {
    appendTurn('user', <p>{text}</p>)
    const result = await chatAgent.sendMessage(text)
    if (result.ok) {
      appendTurn('assistant', <p>{result.response}</p>)
    } else {
      appendTurn('assistant', <p className="chat-error-text">{result.error}</p>)
    }
  }

  const renderAgentBottom = () => {
    const { step, phase } = agentFlow

    if (phase === 'confirm') {
      if (step.kind === 'questionnaire') {
        return (
          <ChatTurn role="assistant" wide>
            <p className="chat-turn-label">Agent's next step</p>
            <p>{step.description}</p>
            <FormatQuestionnaire onSubmit={handleAgentFormatSubmit} submitLabel="Confirm" />
          </ChatTurn>
        )
      }
      return (
        <ChatTurn role="assistant" wide>
          <AgentStepPrompt description={step.description} onConfirm={handleAgentStepConfirm} />
        </ChatTurn>
      )
    }

    return (
      <ChatTurn role="assistant" wide>
        <AgentContinueBar
          showContinue={phase !== 'done'}
          onContinue={agentFlow.continueNext}
          onChat={() => setChatOpen(true)}
        />
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
          disabled={chatAgent.sending}
          placeholder="Ask the agent a question…"
        />
      )}
    </div>
  )
}
