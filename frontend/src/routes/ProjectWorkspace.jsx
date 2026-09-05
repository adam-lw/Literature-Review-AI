import { useCallback, useEffect, useLayoutEffect, useMemo, useState } from 'react'
import { useParams } from 'react-router-dom'
import { useProjects } from '../context/ProjectsContext.jsx'
import { useWorkspaceMode } from '../context/WorkspaceModeContext.jsx'
import { paperListMemory, scopingMemory } from '../api/agentClient.js'
import CriteriaEditor from '../components/CriteriaEditor.jsx'
import ResultsPanel from '../components/ResultsPanel.jsx'
import ChatTurn from '../components/chat/ChatTurn.jsx'
import ActionBar from '../components/chat/ActionBar.jsx'
import ChatComposer from '../components/chat/ChatComposer.jsx'
import FormatQuestionnaire from '../components/chat/FormatQuestionnaire.jsx'
import PlaceholderNotice from '../components/chat/PlaceholderNotice.jsx'
import AgentContinueBar from '../components/chat/AgentContinueBar.jsx'
import AgentQuestion from '../components/chat/AgentQuestion.jsx'
import AgentThoughts from '../components/chat/AgentThoughts.jsx'
import ScopeSummary from '../components/chat/ScopeSummary.jsx'
import { AGENT_PHASES, useAgentPhaseFlow } from '../components/chat/useAgentPhaseFlow.js'
import { useAgentConversation } from '../components/chat/useAgentConversation.js'
import { tryParseScope } from '../components/chat/scopeMemory.js'

export default function ProjectWorkspace() {
  const { id } = useParams()
  const { store, refreshProjects } = useProjects()
  const { workspaceMode, setWorkspaceMode, clearWorkspaceMode } = useWorkspaceMode()
  const [project, setProject] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [titleDraft, setTitleDraft] = useState('')
  const [editingTitle, setEditingTitle] = useState(false)
  const [newTerm, setNewTerm] = useState('')
  const [addingTerm, setAddingTerm] = useState(false)
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

  // This project defaults to Manual mode every time it's (re-)opened; the slider can flip
  // it to Agent mode from here on, live, for the rest of this visit.
  useLayoutEffect(() => {
    setWorkspaceMode('manual')
    return () => clearWorkspaceMode()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id])

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const p = await store.getProject(id)
      if (!p) {
        setError('Project not found.')
      } else {
        setProject(p)
        setTitleDraft(p.project_title)
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [store, id])

  useEffect(() => {
    load()
    setConversation([])
    setChatOpen(false)
    setPhaseStarted(false)
    setScopeSpecification(null)
    phaseAgent.reset()
    phaseChatAgent.reset()
    chatAgent.reset()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [load])

  const dedupeCounts = useMemo(() => {
    if (!project) return {}
    const counts = {}
    for (const search of project.searches) {
      for (const result of search.results) {
        counts[result.paper_id] = (counts[result.paper_id] || 0) + 1
      }
    }
    return counts
  }, [project])

  const totals = useMemo(() => {
    if (!project) return { searches: 0, papers: 0, included: 0 }
    const papers = project.searches.reduce((sum, s) => sum + s.results.length, 0)
    const included = project.searches.reduce(
      (sum, s) => sum + s.results.filter((r) => r.included).length,
      0,
    )
    return { searches: project.searches.length, papers, included }
  }, [project])

  // Paper context to hand agents alongside the message history. Only included papers are sent,
  // matching the "ask about the N included papers" framing shown in the chat prompt.
  const includedPaperMemory = useMemo(() => {
    if (!project) return undefined
    const papers = project.searches.flatMap((s) =>
      s.results
        .filter((r) => r.included)
        .map((r) => ({
          paperId: r.paper_id,
          title: r.title,
          abstract: r.abstract,
          year: r.year,
          venue: r.venue,
          citationCount: r.citation_count,
          url: r.url,
          DOI: r.doi,
        })),
    )
    return papers.length > 0 ? [paperListMemory('included_papers', papers)] : undefined
  }, [project])

  // Every phase after scoping (and every phase's chat) gets the finalized scope spec as memory,
  // once one exists, alongside the included papers.
  const buildPhaseMemory = () => {
    const memory = [...(includedPaperMemory ?? [])]
    if (scopeSpecification) memory.push(scopingMemory(scopeSpecification))
    return memory.length > 0 ? memory : undefined
  }

  const appendTurn = useCallback((role, node) => {
    setConversation((prev) => [...prev, { id: crypto.randomUUID(), role, node }])
  }, [])

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

  const commitCriteria = async (value) => {
    if (!project || value === (project.inclusion_criteria ?? '')) return
    const updated = await store.updateProject(id, { inclusion_criteria: value || null })
    setProject(updated)
  }

  const handleAddTerm = async (e) => {
    e.preventDefault()
    const query = newTerm.trim()
    if (!query || addingTerm) return
    setAddingTerm(true)
    try {
      const search = await store.addSearchTerm(id, query, 10)
      setProject((prev) => {
        if (prev.searches.some((s) => s.search_id === search.search_id)) return prev
        return { ...prev, searches: [...prev.searches, search] }
      })
      setNewTerm('')
      refreshProjects()
    } catch (err) {
      setError(err.message)
    } finally {
      setAddingTerm(false)
    }
  }

  const handleToggleInclude = async (resultId, included) => {
    setProject((prev) => ({
      ...prev,
      searches: prev.searches.map((s) => ({
        ...s,
        results: s.results.map((r) => (r.result_id === resultId ? { ...r, included } : r)),
      })),
    }))
    await store.setInclusion(id, resultId, included)
    refreshProjects()
  }

  const handleSetAll = async (searchId, included) => {
    const search = project.searches.find((s) => s.search_id === searchId)
    const items = search.results.map((r) => ({ result_id: r.result_id, included }))
    setProject((prev) => ({
      ...prev,
      searches: prev.searches.map((s) =>
        s.search_id === searchId ? { ...s, results: s.results.map((r) => ({ ...r, included })) } : s,
      ),
    }))
    await store.setInclusionBulk(id, items)
    refreshProjects()
  }

  const handleRemoveTerm = async (searchId) => {
    if (!window.confirm('Remove this search term and its results?')) return
    await store.removeSearchTerm(id, searchId)
    setProject((prev) => ({ ...prev, searches: prev.searches.filter((s) => s.search_id !== searchId) }))
    refreshProjects()
  }

  const handleAction = (key) => {
    if (key === 'chat') {
      setChatOpen(true)
      appendTurn(
        'assistant',
        <p>You can ask questions about the {totals.included} included papers below.</p>,
      )
      return
    }
    if (key === 'summary') {
      appendTurn('user', <p>Generate a summary of the {totals.included} included papers.</p>)
      appendTurn(
        'assistant',
        <PlaceholderNotice
          feature="Summary generation"
          detail={`Once available, this will produce a synthesised summary of the ${totals.included} papers you've included.`}
        />,
      )
      return
    }
    if (key === 'gaps') {
      appendTurn('user', <p>Find research gaps across the included papers.</p>)
      appendTurn(
        'assistant',
        <PlaceholderNotice
          feature="Research gap analysis"
          detail="Once available, this will surface themes and methods that the included papers don't yet cover."
        />,
      )
      return
    }
    if (key === 'lit-review') {
      appendTurn('user', <p>Write a full literature review from the included papers.</p>)
      appendTurn(
        'assistant',
        <div>
          <p>How would you like the review formatted?</p>
          <FormatQuestionnaire
            onSubmit={({ citationStyle, sections }) => {
              appendTurn(
                'user',
                <p>
                  {citationStyle} format, sections: {sections.join(', ')}.
                </p>,
              )
              appendTurn(
                'assistant',
                <PlaceholderNotice
                  feature="Literature review writing"
                  detail={`The writing agent will draft a review formatted in ${citationStyle} style, covering: ${sections.join(', ')}.`}
                />,
              )
            }}
          />
        </div>,
      )
    }
  }

  // Renders one phase agent's completed/error response as a transcript turn: a "Thoughts"
  // disclosure when the turn carried reasoning, then either a friendly scope summary card (when
  // the scoping phase just finalized/updated its specification - see `tryParseScope`) or its
  // plain text. An "awaiting_input" response leaves the transcript untouched - the interactive
  // `AgentQuestion` card in `renderAgentBottom` is the sole representation of a pending question,
  // and `handlePhaseMessage` commits it to history once it's actually answered.
  const appendPhaseResult = (result) => {
    if (!result.ok) {
      appendTurn('assistant', <p className="chat-error-text">{result.error}</p>)
      return
    }
    const { response } = result
    if (response.status === 'awaiting_input') return

    const scope = agentFlow.phase?.key === 'scoping' ? tryParseScope(response.response) : null
    if (scope) setScopeSpecification(scope)

    appendTurn(
      'assistant',
      <>
        {response.reasoning && <AgentThoughts text={response.reasoning} />}
        {scope ? <ScopeSummary specification={scope} /> : <p>{response.response}</p>}
      </>,
    )
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

  // Commits the just-answered question's title to history (the `AgentQuestion` card that showed
  // it has already collapsed by the time this fires - see `AgentQuestion.jsx`), then the user's
  // answer, before continuing the conversation.
  const handlePhaseMessage = async (text) => {
    if (phaseAgent.question) {
      appendTurn('assistant', <p>{phaseAgent.question.question}</p>)
    }
    appendTurn('user', <p>{text}</p>)
    appendPhaseResult(await phaseAgent.send(text, buildPhaseMemory()))
  }

  // Every phase starts itself automatically - there's no separate "confirm before starting"
  // box, only the continue bar shown once a phase's questions are done.
  useEffect(() => {
    if (workspaceMode === 'agent' && project && agentFlow.phase && !phaseStarted) {
      handleStartPhase()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [workspaceMode, project, agentFlow.phase, phaseStarted])

  const handleContinuePhase = () => {
    phaseAgent.reset()
    phaseChatAgent.reset()
    setPhaseStarted(false)
    agentFlow.advance()
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
    const scope =
      chatPhase.key === 'scoping' && response.status === 'completed'
        ? tryParseScope(response.response)
        : null
    if (scope) setScopeSpecification(scope)

    appendTurn(
      'assistant',
      <>
        {response.reasoning && <AgentThoughts text={response.reasoning} />}
        {response.status === 'awaiting_input' ? (
          <p>{response.question.question}</p>
        ) : scope ? (
          <ScopeSummary specification={scope} />
        ) : (
          <p>{response.response}</p>
        )}
      </>,
    )
  }

  // In manual mode this talks to the standalone "chatbot" agent; in agent mode it's the current
  // phase's dedicated chat conversation.
  const handleChatSend = async (text) => {
    if (workspaceMode === 'agent') return handlePhaseChatMessage(text)

    appendTurn('user', <p>{text}</p>)
    const result =
      chatAgent.status === null
        ? await chatAgent.start('chatbot', text, includedPaperMemory)
        : await chatAgent.send(text, includedPaperMemory)
    if (result.ok) {
      appendTurn(
        'assistant',
        <>
          {result.response.reasoning && <AgentThoughts text={result.response.reasoning} />}
          <p>{result.response.response}</p>
        </>,
      )
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

  if (loading) return <p className="page-status">Loading project…</p>
  if (error) return <p className="page-status error">{error}</p>
  if (!project) return null

  const queryChips = project.searches.map((s) => s.query)

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
          {totals.searches} searches · {totals.papers} papers · {totals.included} included
        </div>
      </header>

      <div className="workspace-thread">
        {queryChips.length > 0 && (
          <ChatTurn role="user">
            <p className="turn-lede">Searched for:</p>
            <div className="query-chip-row">
              {queryChips.map((q) => (
                <span key={q} className="query-chip">
                  {q}
                </span>
              ))}
            </div>
          </ChatTurn>
        )}

        <ChatTurn role="assistant" wide>
          <label className="field-label">Inclusion / exclusion criteria</label>
          <CriteriaEditor
            value={project.inclusion_criteria}
            onChange={(v) => setProject((prev) => ({ ...prev, inclusion_criteria: v }))}
            onBlur={(e) => commitCriteria(e.target.value)}
          />

          <form className="add-term-form" onSubmit={handleAddTerm}>
            <input
              type="text"
              placeholder="Add another search term…"
              value={newTerm}
              onChange={(e) => setNewTerm(e.target.value)}
            />
            <button type="submit" disabled={addingTerm || !newTerm.trim()}>
              {addingTerm ? 'Searching…' : 'Add term'}
            </button>
          </form>

          <ResultsPanel
            searches={project.searches}
            dedupeCounts={dedupeCounts}
            onToggleInclude={handleToggleInclude}
            onSetAll={handleSetAll}
            onRemoveTerm={handleRemoveTerm}
          />
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

        {workspaceMode === 'manual' && totals.papers > 0 && (
          <ChatTurn role="assistant" wide>
            <p className="turn-lede">What would you like to do next?</p>
            <ActionBar onAction={handleAction} />
          </ChatTurn>
        )}

        {workspaceMode === 'agent' && renderAgentBottom()}
      </div>

      {chatOpen && (
        <ChatComposer
          onSend={handleChatSend}
          disabled={workspaceMode === 'agent' ? phaseAgent.sending || phaseChatAgent.sending : chatAgent.sending}
          placeholder="Ask about the collected findings…"
        />
      )}
    </div>
  )
}
