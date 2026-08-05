import { useCallback, useEffect, useMemo, useState } from 'react'
import { useParams } from 'react-router-dom'
import { useProjects } from '../context/ProjectsContext.jsx'
import CriteriaEditor from '../components/CriteriaEditor.jsx'
import SearchTermGroup from '../components/SearchTermGroup.jsx'
import EmptyState from '../components/EmptyState.jsx'

export default function ResultsPage() {
  const { id } = useParams()
  const { store, refreshProjects } = useProjects()
  const [project, setProject] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [titleDraft, setTitleDraft] = useState('')
  const [editingTitle, setEditingTitle] = useState(false)
  const [newTerm, setNewTerm] = useState('')
  const [addingTerm, setAddingTerm] = useState(false)

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

  if (loading) return <p className="page-status">Loading project…</p>
  if (error) return <p className="page-status error">{error}</p>
  if (!project) return null

  return (
    <div className="results-page">
      <header className="results-header">
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
        <div className="results-totals">
          {totals.searches} searches · {totals.papers} papers · {totals.included} included
        </div>
        <div className="results-header-actions">
          <button type="button" disabled title="Not yet implemented">
            Agentic include/exclude
          </button>
          <button type="button" disabled title="Not yet implemented">
            Writing agent — coming soon
          </button>
        </div>
      </header>

      <section className="criteria-section">
        <label className="field-label">Inclusion / exclusion criteria</label>
        <CriteriaEditor
          value={project.inclusion_criteria}
          onChange={(v) => setProject((prev) => ({ ...prev, inclusion_criteria: v }))}
          onBlur={(e) => commitCriteria(e.target.value)}
        />
      </section>

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

      {project.searches.length === 0 ? (
        <EmptyState title="No search terms yet" description="Add a term above to start finding papers." />
      ) : (
        project.searches.map((search) => (
          <SearchTermGroup
            key={search.search_id}
            search={search}
            dedupeCounts={dedupeCounts}
            onToggleInclude={handleToggleInclude}
            onSetAll={handleSetAll}
            onRemoveTerm={handleRemoveTerm}
          />
        ))
      )}
    </div>
  )
}
