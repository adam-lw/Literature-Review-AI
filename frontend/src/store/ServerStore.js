import { apiClient } from '../api/client.js'

// Normalises a server ProjectOut/ProjectSummaryOut into the shape shared across the app - just
// renames `project_mode` (the backend's persisted, truthful field) to `mode`, the name every
// route/component already reads (ProjectSidebar, AgentProjectWorkspace, ...). Every project -
// agent-created or human-created alike - is a real `app.projects` row now, so this store is the
// single source for both; there is no separate agent-project store any more.
function normaliseProject(p) {
  return { ...p, mode: p.project_mode }
}

export const ServerStore = {
  async listProjects() {
    const { projects } = await apiClient.get('/projects')
    return projects.map(normaliseProject)
  },

  async createProject({ queries, embedding_run_id, inclusion_criteria, n_results }) {
    const project = await apiClient.post('/projects', {
      queries,
      embedding_run_id,
      inclusion_criteria,
      n_results,
    })
    return normaliseProject(project)
  },

  async createAgentProject({ inclusion_criteria, project_title }) {
    const project = await apiClient.post('/projects/agent-mode', {
      inclusion_criteria,
      project_title,
    })
    return normaliseProject(project)
  },

  async createAgentProjectFromScope(scopeId) {
    const project = await apiClient.post('/projects/agent-mode/from-scope', { scope_id: scopeId })
    return normaliseProject(project)
  },

  async getProject(id) {
    const project = await apiClient.get(`/projects/${id}`)
    return normaliseProject(project)
  },

  async updateProject(id, patch) {
    const project = await apiClient.patch(`/projects/${id}`, patch)
    return normaliseProject(project)
  },

  async deleteProject(id) {
    await apiClient.delete(`/projects/${id}`)
  },

  async addSearchTerm(projectId, query, nResults) {
    return apiClient.post(`/projects/${projectId}/searches`, { query, n_results: nResults })
  },

  async removeSearchTerm(projectId, searchId) {
    await apiClient.delete(`/projects/${projectId}/searches/${searchId}`)
  },

  async setInclusion(_projectId, resultId, included) {
    await apiClient.patch(`/results/${resultId}/inclusion`, { included })
  },

  async setInclusionBulk(projectId, items) {
    await apiClient.patch(`/projects/${projectId}/inclusion`, { items })
  },

  async listEmbeddingRuns() {
    const { runs } = await apiClient.get('/embedding-models')
    return runs
  },

  // Persisted 3-phase flow, backed by app.conversations/app.messages/app.scopes/app.reviews.
  // The agent service (agent_service/api/routers/invoke_agent.py) writes none of this itself -
  // it hands back what a turn produced (new_messages/scope/reviews on its response), and
  // `usePhaseAgent.send` calls the relevant methods below to persist it, right after getting it.
  async getConversations(projectId) {
    return apiClient.get(`/projects/${projectId}/conversations`)
  },

  async addConversationMessages(projectId, stage, messages) {
    return apiClient.post(`/projects/${projectId}/conversations/${stage}/messages`, { messages })
  },

  async getScope(projectId) {
    return apiClient.get(`/projects/${projectId}/scope`)
  },

  async setScope(projectId, content) {
    return apiClient.put(`/projects/${projectId}/scope`, { content })
  },

  async setReviews(projectId, reviews) {
    return apiClient.put(`/projects/${projectId}/reviews`, { reviews })
  },

  async setConversationCompleted(projectId, stage, completed) {
    return apiClient.patch(`/projects/${projectId}/conversations/${stage}`, { completed })
  },

  async setScopeMetadata(projectId, { scope_title, scope_description }) {
    return apiClient.patch(`/projects/${projectId}/scope`, { scope_title, scope_description })
  },

  // Recently-finalized scopes across all projects, for the agent landing page's "start review
  // from an existing scope" list - ranked by recency, optionally filtered by a search term.
  async listRecentScopes(search) {
    const query = search ? `?search=${encodeURIComponent(search)}` : ''
    const { scopes } = await apiClient.get(`/scopes${query}`)
    return scopes
  },
}
