import { createContext, useCallback, useContext, useMemo, useState } from 'react'

// Lets the header's mode slider mean two different things depending on where you are:
// on a landing page there is no active project, so the slider just picks which landing
// form to show (handled by ModeToggle navigating between /new/manual and /new/agent).
// Once a project workspace mounts, it registers itself here so the *same* slider instead
// flips that project's live mode — see ProjectWorkspace/AgentProjectWorkspace.
const WorkspaceModeContext = createContext(null)

export function WorkspaceModeProvider({ children }) {
  const [workspaceMode, setWorkspaceMode] = useState(null)

  const clearWorkspaceMode = useCallback(() => setWorkspaceMode(null), [])

  const value = useMemo(
    () => ({ workspaceMode, setWorkspaceMode, clearWorkspaceMode }),
    [workspaceMode, clearWorkspaceMode],
  )

  return <WorkspaceModeContext.Provider value={value}>{children}</WorkspaceModeContext.Provider>
}

export function useWorkspaceMode() {
  const ctx = useContext(WorkspaceModeContext)
  if (!ctx) throw new Error('useWorkspaceMode must be used within a WorkspaceModeProvider')
  return ctx
}
