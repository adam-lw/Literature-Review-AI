import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useProjects } from '../context/ProjectsContext.jsx'
import { generateTitle } from '../api/agentClient.js'
import RecentScopesPanel from '../components/RecentScopesPanel.jsx'

export default function AgentLandingPage() {
  const navigate = useNavigate()
  const { createAgentProject } = useProjects()
  const [description, setDescription] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const canSubmit = description.trim().length > 0 && !submitting

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!canSubmit) return
    setSubmitting(true)
    const trimmedDescription = description.trim()
    let project_title
    try {
      project_title = await generateTitle(trimmedDescription)
    } catch {
      // Title generation is best-effort - fall back to the local store's placeholder title.
    }
    const project = await createAgentProject({
      inclusion_criteria: null,
      project_title,
    })
    // Not persisted server-side - it's sent as the scoping phase's opening instruction the first
    // time it starts (see AgentProjectWorkspace.jsx), which is also where it ends up logged.
    navigate(`/agent-projects/${project.project_id}`, { state: { initialDescription: trimmedDescription } })
  }

  return (
    <div className="landing-page">
      <div className="landing-hero">
        <h1>Describe the research you'd like to undertake</h1>
        <p className="landing-subtitle">
          The agent will derive search terms from your description, collect candidate papers, and
          evaluate each one against your inclusion criteria.
        </p>
      </div>

      <form className="agent-form" onSubmit={handleSubmit}>
        <label className="field-label">Research description</label>
        <textarea
          className="agent-textarea"
          rows={8}
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="e.g. A review of transformer-based approaches to low-resource machine translation published since 2020…"
        />

        <button type="submit" className="submit-btn" disabled={!canSubmit}>
          {submitting ? 'Starting…' : 'Start agent project'}
        </button>
      </form>

      <RecentScopesPanel />
    </div>
  )
}
