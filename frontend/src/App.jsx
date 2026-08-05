import { HashRouter, Navigate, Route, Routes } from 'react-router-dom'
import { ProjectsProvider } from './context/ProjectsContext.jsx'
import AppShell from './components/AppShell.jsx'
import HitlLandingPage from './routes/HitlLandingPage.jsx'
import AgentLandingPage from './routes/AgentLandingPage.jsx'
import ResultsPage from './routes/ResultsPage.jsx'

export default function App() {
  return (
    <ProjectsProvider>
      <HashRouter>
        <Routes>
          <Route element={<AppShell />}>
            <Route path="/" element={<Navigate to="/new/hitl" replace />} />
            <Route path="/new/hitl" element={<HitlLandingPage />} />
            <Route path="/new/agent" element={<AgentLandingPage />} />
            <Route path="/projects/:id" element={<ResultsPage />} />
          </Route>
        </Routes>
      </HashRouter>
    </ProjectsProvider>
  )
}
