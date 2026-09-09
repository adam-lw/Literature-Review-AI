// Server-backed projects (`/projects/:id`, routes/ProjectWorkspace.jsx) have no backend field for
// the agent-mode chat transcript - `ProjectUpdateRequest` (literature_ai/app/api/models.py) only
// knows project_title/description/inclusion_criteria/embedding_run_id, and Pydantic silently
// drops anything else sent to PATCH /projects/{id}. So this workspace's chat state is kept
// client-side only, the same way AgentLocalStore keeps whole agent projects - keyed by project
// id, surviving reloads and project switches within this browser.
const STORAGE_KEY = 'literature-ai:workspace-chat-state'

function readAll() {
  const raw = localStorage.getItem(STORAGE_KEY)
  return raw ? JSON.parse(raw) : {}
}

function writeAll(byProjectId) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(byProjectId))
}

export const WorkspaceChatStore = {
  get(projectId) {
    return readAll()[projectId] ?? null
  },

  set(projectId, state) {
    const all = readAll()
    all[projectId] = state
    writeAll(all)
  },
}
