import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useProjects } from '../context/ProjectsContext.jsx'
import QueryListInput from '../components/QueryListInput.jsx'
import EmbeddingRunSelect from '../components/EmbeddingRunSelect.jsx'
import CriteriaEditor from '../components/CriteriaEditor.jsx'

export default function ManualLandingPage() {
  const navigate = useNavigate()
  const { createProject } = useProjects()
  const [queries, setQueries] = useState([''])
  const [embeddingRunId, setEmbeddingRunId] = useState(null)
  const [criteria, setCriteria] = useState('')
  const [nResults, setNResults] = useState(10)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState(null)

  const nonBlankQueries = queries.map((q) => q.trim()).filter(Boolean)
  const canSubmit = nonBlankQueries.length > 0 && embeddingRunId != null && !submitting

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!canSubmit) return
    setSubmitting(true)
    setError(null)
    try {
      const project = await createProject({
        queries: nonBlankQueries,
        embedding_run_id: embeddingRunId,
        inclusion_criteria: criteria.trim() || null,
        n_results: nResults,
      })
      navigate(`/projects/${project.project_id}`)
    } catch (err) {
      setError(err.message)
      setSubmitting(false)
    }
  }

  return (
    <div className="landing-page">
      <div className="landing-hero">
        <h1>Start a new literature search</h1>
        <p className="landing-subtitle">
          Enter one or more search terms and we'll retrieve candidate papers for you to review, expand,
          and select for inclusion.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="manual-form">
        <label className="field-label">Search terms</label>
        <QueryListInput onChange={setQueries} />

        <label className="field-label">Search model</label>
        <EmbeddingRunSelect value={embeddingRunId} onChange={setEmbeddingRunId} />

        <label className="field-label">Inclusion / exclusion criteria (optional)</label>
        <CriteriaEditor value={criteria} onChange={setCriteria} />

        <label className="field-label">Results per term</label>
        <input
          type="number"
          min={1}
          max={100}
          value={nResults}
          onChange={(e) => setNResults(Number(e.target.value))}
          className="n-results-input"
        />

        {error && <p className="form-error">{error}</p>}

        <button type="submit" className="submit-btn" disabled={!canSubmit}>
          {submitting ? 'Searching…' : 'Start project'}
        </button>
      </form>
    </div>
  )
}
