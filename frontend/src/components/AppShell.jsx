import { Outlet } from 'react-router-dom'
import ModeToggle from './ModeToggle.jsx'
import ThemeToggle from './ThemeToggle.jsx'
import ProjectSidebar from './ProjectSidebar.jsx'

export default function AppShell() {
  return (
    <div className="app-shell">
      <header className="app-header">
        <span className="app-name">Literature AI</span>
        <ModeToggle />
        <ThemeToggle />
      </header>
      <div className="app-body">
        <ProjectSidebar />
        <main className="app-content">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
