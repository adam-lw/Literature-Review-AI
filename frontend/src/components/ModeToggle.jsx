import { useLocation, useNavigate } from 'react-router-dom'
import { useWorkspaceMode } from '../context/WorkspaceModeContext.jsx'

export default function ModeToggle() {
  const location = useLocation()
  const navigate = useNavigate()
  const { workspaceMode, setWorkspaceMode } = useWorkspaceMode()

  const inWorkspace = workspaceMode != null
  const mode = inWorkspace ? workspaceMode : location.pathname.startsWith('/new/agent') ? 'agent' : 'manual'

  const toggle = () => {
    const next = mode === 'manual' ? 'agent' : 'manual'
    if (inWorkspace) {
      setWorkspaceMode(next)
    } else {
      navigate(`/new/${next}`)
    }
  }

  return (
    <div className="mode-slider" title="Switch between manual and agent mode">
      <span className={`mode-slider-label ${mode === 'manual' ? 'active' : ''}`}>Manual</span>
      <span
        className="mode-slider-track"
        role="switch"
        aria-checked={mode === 'agent'}
        aria-label="Switch between manual and agent mode"
        tabIndex={0}
        onClick={toggle}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault()
            toggle()
          }
        }}
      >
        <span className={`mode-slider-thumb ${mode === 'agent' ? 'right' : ''}`} />
      </span>
      <span className={`mode-slider-label ${mode === 'agent' ? 'active' : ''}`}>Agent</span>
    </div>
  )
}
