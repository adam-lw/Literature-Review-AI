import { apiClient } from '../api/client.js'

// Normalises a server ProjectOut/ProjectSummaryOut into the shape shared by both stores.
// The backend never returns a `mode` field (see literature_ai/app/api/models.py) — every
// project reachable through this store was created via the HITL flow, since the agent flow's
// submit button never fires a request, so 'hitl' is a safe constant here rather than a guess.
function normaliseProject(p) {
  return { ...p, mode: 'hitl' }
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
}
