import { createContext, useCallback, useContext, useEffect, useReducer } from 'react'
import { store, isDemoMode } from '../store/index.js'

const ProjectsContext = createContext(null)

const initialState = {
  projects: [],
  projectsLoading: true,
  projectsError: null,
  embeddingRuns: [],
  embeddingRunsLoading: true,
  embeddingRunsError: null,
}

function reducer(state, action) {
  switch (action.type) {
    case 'projects/loading':
      return { ...state, projectsLoading: true, projectsError: null }
    case 'projects/loaded':
      return { ...state, projects: action.projects, projectsLoading: false }
    case 'projects/error':
      return { ...state, projectsLoading: false, projectsError: action.error }
    case 'runs/loading':
      return { ...state, embeddingRunsLoading: true, embeddingRunsError: null }
    case 'runs/loaded':
      return { ...state, embeddingRuns: action.runs, embeddingRunsLoading: false }
    case 'runs/error':
      return { ...state, embeddingRunsLoading: false, embeddingRunsError: action.error }
    default:
      return state
  }
}

export function ProjectsProvider({ children }) {
  const [state, dispatch] = useReducer(reducer, initialState)

  const refreshProjects = useCallback(async () => {
    dispatch({ type: 'projects/loading' })
    try {
      const projects = await store.listProjects()
      dispatch({ type: 'projects/loaded', projects })
    } catch (error) {
      dispatch({ type: 'projects/error', error: error.message })
    }
  }, [])

  const refreshEmbeddingRuns = useCallback(async () => {
    dispatch({ type: 'runs/loading' })
    try {
      const runs = await store.listEmbeddingRuns()
      dispatch({ type: 'runs/loaded', runs })
    } catch (error) {
      dispatch({ type: 'runs/error', error: error.message })
    }
  }, [])

  useEffect(() => {
    refreshProjects()
    refreshEmbeddingRuns()
  }, [refreshProjects, refreshEmbeddingRuns])

  const createProject = useCallback(
    async (payload) => {
      const project = await store.createProject(payload)
      await refreshProjects()
      return project
    },
    [refreshProjects],
  )

  const deleteProject = useCallback(
    async (id) => {
      await store.deleteProject(id)
      await refreshProjects()
    },
    [refreshProjects],
  )

  const value = {
    ...state,
    isDemoMode,
    store,
    refreshProjects,
    refreshEmbeddingRuns,
    createProject,
    deleteProject,
  }

  return <ProjectsContext.Provider value={value}>{children}</ProjectsContext.Provider>
}

export function useProjects() {
  const ctx = useContext(ProjectsContext)
  if (!ctx) throw new Error('useProjects must be used within a ProjectsProvider')
  return ctx
}
