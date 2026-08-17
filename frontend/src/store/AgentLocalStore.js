// Agent-mode "projects" have no backend support yet (see literature_ai/app/api/routers/projects.py —
// there is no endpoint that accepts a free-text research description). Until that exists, agent
// projects live entirely in localStorage so the sidebar and workspace still have somewhere to
// read/write from, and survive a page reload.
const STORAGE_KEY = 'literature-ai:agent-projects'

function placeholderProjectTitle() {
  const now = new Date()
  const pad = (n) => String(n).padStart(2, '0')
  const date = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`
  const time = `${pad(now.getHours())}:${pad(now.getMinutes())}`
  return `Untitled agent project (${date} ${time})`
}

function readAll() {
  const raw = localStorage.getItem(STORAGE_KEY)
  return raw ? JSON.parse(raw) : []
}

function writeAll(projects) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(projects))
}

function summarise(p) {
  return {
    project_id: p.project_id,
    project_title: p.project_title,
    mode: 'agent',
    created_at: p.created_at,
    search_count: 0,
    paper_count: 0,
    included_count: 0,
  }
}

export const AgentLocalStore = {
  listProjects() {
    return readAll().map(summarise)
  },

  getProject(id) {
    return readAll().find((p) => p.project_id === id) ?? null
  },

  createProject({ description, inclusion_criteria }) {
    const now = new Date().toISOString()
    const project = {
      project_id: crypto.randomUUID(),
      project_title: placeholderProjectTitle(),
      mode: 'agent',
      description,
      inclusion_criteria: inclusion_criteria || null,
      created_at: now,
      updated_at: now,
      stage: 'reviewing',
      formatPreferences: null,
      conversation: [],
    }
    const projects = readAll()
    projects.unshift(project)
    writeAll(projects)
    return project
  },

  updateProject(id, patch) {
    const projects = readAll()
    const project = projects.find((p) => p.project_id === id)
    if (!project) throw new Error(`No agent project found for project_id=${id}`)
    Object.assign(project, patch, { updated_at: new Date().toISOString() })
    writeAll(projects)
    return project
  },

  deleteProject(id) {
    writeAll(readAll().filter((p) => p.project_id !== id))
  },
}
