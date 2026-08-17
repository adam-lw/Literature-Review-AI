import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useProjects } from '../context/ProjectsContext.jsx'
import CriteriaEditor from '../components/CriteriaEditor.jsx'

export default function AgentLandingPage() {
  const navigate = useNavigate()
  const { createAgentProject } = useProjects()
  const [description, setDescription] = useState('')
  const [criteria, setCriteria] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const canSubmit = description.trim().length > 0 && !submitting

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!canSubmit) return
    setSubmitting(true)
    const project = await createAgentProject({
      description: description.trim(),
      inclusion_criteria: criteria.trim() || null,
    })
    navigate(`/agent-projects/${project.project_id}`)
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

        <label className="field-label">Inclusion / exclusion criteria (optional)</label>
        <CriteriaEditor value={criteria} onChange={setCriteria} />

        <button type="submit" className="submit-btn" disabled={!canSubmit}>
          {submitting ? 'Starting…' : 'Start agent project'}
        </button>
      </form>
    </div>
  )
}
