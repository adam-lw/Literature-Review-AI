import { useLocation, useNavigate, useParams } from 'react-router-dom'
import { useProjects } from '../context/ProjectsContext.jsx'
import { relativeDate } from '../utils/relativeDate.js'
import DemoBanner from './DemoBanner.jsx'

export default function ProjectSidebar() {
  const { projects, projectsLoading, projectsError, deleteProject, isDemoMode } = useProjects()
  const navigate = useNavigate()
  const location = useLocation()
  const { id: activeId } = useParams()
  const currentMode =
    location.pathname.startsWith('/new/agent') || location.pathname.startsWith('/agent-projects')
      ? 'agent'
      : 'manual'

  const projectPath = (project) =>
    project.mode === 'agent' ? `/agent-projects/${project.project_id}` : `/projects/${project.project_id}`

  const handleDelete = async (event, project) => {
    event.stopPropagation()
    if (!window.confirm('Delete this project? This cannot be undone.')) return
    await deleteProject(project.project_id)
    if (activeId === project.project_id) navigate('/new/manual')
  }

  return (
    <aside className="project-sidebar">
      {isDemoMode && <DemoBanner />}
      <button type="button" className="new-project-btn" onClick={() => navigate(`/new/${currentMode}`)}>
        + New project
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
            onClick={() => navigate(projectPath(project))}
          >
            <div className="project-list-row">
              <span className="project-title">{project.project_title}</span>
              <span className={`mode-badge mode-${project.mode}`}>
                {project.mode === 'agent' ? 'Agent' : 'Manual'}
              </span>
            </div>
            <div className="project-meta">
              {relativeDate(project.created_at)}
              {project.mode !== 'agent' &&
                ` · ${project.search_count} searches · ${project.paper_count} papers · ${project.included_count} included`}
            </div>
            <button
              type="button"
              className="delete-project-btn"
              title="Delete project"
              onClick={(e) => handleDelete(e, project)}
            >
              ×
            </button>
          </li>
        ))}
      </ul>
    </aside>
  )
}
