import { apiClient } from '../api/client.js'

const STORAGE_KEY = 'literature-ai:demo-projects'

// Reproduces literature_ai/app/persistence_handling.py::placeholder_project_title() verbatim —
// this exact format is a contract shared with the server (see planA.md §3 / planB.md §2), not a
// convention this file owns. Do not reformat without checking both places.
function placeholderProjectTitle() {
  const now = new Date()
  const pad = (n) => String(n).padStart(2, '0')
  const date = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`
  const time = `${pad(now.getHours())}:${pad(now.getMinutes())}`
  return `Untitled project (${date} ${time})`
}

function readAll() {
  const raw = sessionStorage.getItem(STORAGE_KEY)
  return raw ? JSON.parse(raw) : []
}

function writeAll(projects) {
  sessionStorage.setItem(STORAGE_KEY, JSON.stringify(projects))
}

function findProject(projects, id) {
  const project = projects.find((p) => p.project_id === id)
  if (!project) throw new Error(`No project found for project_id=${id}`)
  return project
}

function toResult(raw, rank) {
  return {
    result_id: crypto.randomUUID(),
    paper_id: raw.paperId,
    type: 'embedding',
    search_rank: rank,
    distance: raw.distance,
    distance_type: raw.distance_type || 'cosine',
    title: raw.title,
    abstract: raw.abstract,
    year: raw.year,
    venue: raw.venue,
    citation_count: raw.citationCount,
    url: raw.url,
    doi: raw.DOI,
    included: true,
  }
}

async function runSearch(query, runId, nResults) {
  const response = await apiClient.post('/search', { query, run_id: runId, n_results: nResults })
  return response.results.map((r, i) => toResult(r, i + 1))
}

export const SessionStore = {
  async listProjects() {
    return readAll().map((p) => ({
      ...p,
      search_count: p.searches.length,
      paper_count: p.searches.reduce((sum, s) => sum + s.results.length, 0),
      included_count: p.searches.reduce(
        (sum, s) => sum + s.results.filter((r) => r.included).length,
        0,
      ),
    }))
  },

  async createProject({ queries, embedding_run_id, inclusion_criteria, n_results }) {
    const now = new Date().toISOString()
    const project = {
      project_id: crypto.randomUUID(),
      project_title: placeholderProjectTitle(),
      description: null,
      inclusion_criteria: inclusion_criteria ?? null,
      mode: 'hitl',
      embedding_run_id,
      created_at: now,
      updated_at: now,
      searches: [],
    }

    const seen = new Set()
    for (const raw of queries) {
      const query = raw.trim()
      if (!query || seen.has(query)) continue
      seen.add(query)
      const results = await runSearch(query, embedding_run_id, n_results)
      project.searches.push({
        search_id: crypto.randomUUID(),
        project_id: project.project_id,
        query,
        n_results,
        created_at: new Date().toISOString(),
        results,
      })
    }

    const projects = readAll()
    projects.unshift(project)
    writeAll(projects)
    return project
  },

  async getProject(id) {
    const projects = readAll()
    const project = projects.find((p) => p.project_id === id)
    return project ?? null
  },

  async updateProject(id, patch) {
    const projects = readAll()
    const project = findProject(projects, id)
    Object.assign(project, patch, { updated_at: new Date().toISOString() })
    writeAll(projects)
    return project
  },

  async deleteProject(id) {
    const projects = readAll().filter((p) => p.project_id !== id)
    writeAll(projects)
  },

  async addSearchTerm(projectId, query, nResults) {
    const projects = readAll()
    const project = findProject(projects, projectId)
    const trimmed = query.trim()

    const existing = project.searches.find((s) => s.query === trimmed)
    if (existing) return existing

    const results = await runSearch(trimmed, project.embedding_run_id, nResults)
    const search = {
      search_id: crypto.randomUUID(),
      project_id: projectId,
      query: trimmed,
      n_results: nResults,
      created_at: new Date().toISOString(),
      results,
    }
    project.searches.push(search)
    writeAll(projects)
    return search
  },

  async removeSearchTerm(projectId, searchId) {
    const projects = readAll()
    const project = findProject(projects, projectId)
    project.searches = project.searches.filter((s) => s.search_id !== searchId)
    writeAll(projects)
  },

  async setInclusion(projectId, resultId, included) {
    const projects = readAll()
    const project = findProject(projects, projectId)
    for (const search of project.searches) {
      const result = search.results.find((r) => r.result_id === resultId)
      if (result) result.included = included
    }
    writeAll(projects)
  },

  async setInclusionBulk(projectId, items) {
    const projects = readAll()
    const project = findProject(projects, projectId)
    const byId = new Map(items.map((item) => [item.result_id, item.included]))
    for (const search of project.searches) {
      for (const result of search.results) {
        if (byId.has(result.result_id)) result.included = byId.get(result.result_id)
      }
    }
    writeAll(projects)
  },

  async listEmbeddingRuns() {
    const { runs } = await apiClient.get('/embedding-models')
    return runs
  },
}
