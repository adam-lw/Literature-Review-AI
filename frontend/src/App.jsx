import { HashRouter, Navigate, Route, Routes } from 'react-router-dom'
import { ProjectsProvider } from './context/ProjectsContext.jsx'
import { WorkspaceModeProvider } from './context/WorkspaceModeContext.jsx'
import AppShell from './components/AppShell.jsx'
import ManualLandingPage from './routes/ManualLandingPage.jsx'
import AgentLandingPage from './routes/AgentLandingPage.jsx'
import ProjectWorkspace from './routes/ProjectWorkspace.jsx'
import AgentProjectWorkspace from './routes/AgentProjectWorkspace.jsx'

export default function App() {
  return (
    <ProjectsProvider>
      <WorkspaceModeProvider>
        <HashRouter>
          <Routes>
            <Route element={<AppShell />}>
              <Route path="/" element={<Navigate to="/new/manual" replace />} />
              <Route path="/new/manual" element={<ManualLandingPage />} />
              <Route path="/new/agent" element={<AgentLandingPage />} />
              <Route path="/projects/:id" element={<ProjectWorkspace />} />
              <Route path="/agent-projects/:id" element={<AgentProjectWorkspace />} />
            </Route>
          </Routes>
        </HashRouter>
      </WorkspaceModeProvider>
    </ProjectsProvider>
  )
}
