import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useProjects } from '../context/ProjectsContext.jsx'
import { relativeDate } from '../utils/relativeDate.js'
import ScopeSummary from './chat/ScopeSummary.jsx'

// Lets a user skip scoping entirely and jump straight into the review phase from a previously
// finalized scope - default view is the 10 most recent (across all projects), and the search box
// re-queries app.scopes by title/description/source-project-title, still ranked by recency.
export default function RecentScopesPanel() {
  const { store, createAgentProjectFromScope } = useProjects()
  const navigate = useNavigate()
  const [scopes, setScopes] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [search, setSearch] = useState('')
  const [expandedId, setExpandedId] = useState(null)
  const [startingId, setStartingId] = useState(null)

  const load = async (term) => {
    setLoading(true)
    setError(null)
    try {
      setScopes(await store.listRecentScopes(term))
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load('')
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const handleSearchSubmit = (e) => {
    e.preventDefault()
    load(search.trim())
  }

  const handleStartReview = async (scopeId) => {
    setStartingId(scopeId)
    try {
      const project = await createAgentProjectFromScope(scopeId)
      navigate(`/agent-projects/${project.project_id}`)
    } catch (err) {
      setError(err.message)
      setStartingId(null)
    }
  }

  return (
    <div className="recent-scopes-panel">
      <h2 className="field-label">Or start review from a saved scope</h2>

      <form className="scope-search-form" onSubmit={handleSearchSubmit}>
        <input
          type="text"
          placeholder="Search saved scopes…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <button type="submit">Search</button>
      </form>

      {loading && <p className="sidebar-status">Loading scopes…</p>}
      {error && <p className="sidebar-status error">{error}</p>}
      {!loading && !error && scopes.length === 0 && (
        <p className="sidebar-status">No saved scopes yet.</p>
      )}

      <ul className="project-list">
        {scopes.map((scope) => (
          <li
            key={scope.scope_id}
            className={expandedId === scope.scope_id ? 'active' : ''}
            onClick={() => setExpandedId((id) => (id === scope.scope_id ? null : scope.scope_id))}
          >
            <div className="project-list-row">
              <span className="project-title">{scope.scope_title || 'Untitled scope'}</span>
            </div>
            <div className="project-meta">
              {relativeDate(scope.updated_at)} · from “{scope.source_project_title}”
            </div>
            {scope.scope_description && <p className="scope-panel-description">{scope.scope_description}</p>}

            {expandedId === scope.scope_id && (
              <div className="scope-panel-expanded" onClick={(e) => e.stopPropagation()}>
                <ScopeSummary specification={scope.content} />
                <button
                  type="button"
                  className="submit-btn"
                  disabled={startingId === scope.scope_id}
                  onClick={() => handleStartReview(scope.scope_id)}
                >
                  {startingId === scope.scope_id ? 'Starting…' : 'Start review from this scope'}
                </button>
              </div>
            )}
          </li>
        ))}
      </ul>
    </div>
  )
}
