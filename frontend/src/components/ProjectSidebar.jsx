import { useLocation, useNavigate, useParams } from 'react-router-dom'
import { useProjects } from '../context/ProjectsContext.jsx'
import DemoBanner from './DemoBanner.jsx'

function relativeDate(iso) {
  const diffMs = Date.now() - new Date(iso).getTime()
  const diffMin = Math.round(diffMs / 60000)
  if (diffMin < 1) return 'just now'
  if (diffMin < 60) return `${diffMin}m ago`
  const diffHr = Math.round(diffMin / 60)
  if (diffHr < 24) return `${diffHr}h ago`
  const diffDay = Math.round(diffHr / 24)
  return `${diffDay}d ago`
}

export default function ProjectSidebar() {
  const { projects, projectsLoading, projectsError, deleteProject, isDemoMode } = useProjects()
  const navigate = useNavigate()
  const location = useLocation()
  const { id: activeId } = useParams()
  const currentMode = location.pathname.startsWith('/new/agent') ? 'agent' : 'hitl'

  const handleDelete = async (event, projectId) => {
    event.stopPropagation()
    if (!window.confirm('Delete this project? This cannot be undone.')) return
    await deleteProject(projectId)
    if (activeId === projectId) navigate('/new/hitl')
  }

  return (
    <aside className="project-sidebar">
      {isDemoMode && <DemoBanner />}
      <button type="button" className="new-project-btn" onClick={() => navigate(`/new/${currentMode}`)}>
        + New
      </button>

      {projectsLoading && <p className="sidebar-status">Loading projects…</p>}
      {projectsError && <p className="sidebar-status error">{projectsError}</p>}
      {!projectsLoading && !projectsError && projects.length === 0 && (
        <p className="sidebar-status">No projects yet.</p>
      )}

      <ul className="project-list">
        {projects.map((project) => (
          <li
            key={project.project_id}
            className={project.project_id === activeId ? 'active' : ''}
            onClick={() => navigate(`/projects/${project.project_id}`)}
          >
            <div className="project-list-row">
              <span className="project-title">{project.project_title}</span>
              <span className={`mode-badge mode-${project.mode}`}>
                {project.mode === 'agent' ? 'Agent' : 'HITL'}
              </span>
            </div>
            <div className="project-meta">
              {relativeDate(project.created_at)} · {project.search_count} searches ·{' '}
              {project.paper_count} papers · {project.included_count} included
            </div>
            <button
              type="button"
              className="delete-project-btn"
              title="Delete project"
              onClick={(e) => handleDelete(e, project.project_id)}
            >
              ×
            </button>
          </li>
        ))}
      </ul>
    </aside>
  )
}
