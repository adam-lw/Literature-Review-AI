import { useLocation, useNavigate } from 'react-router-dom'

export default function ModeToggle() {
  const location = useLocation()
  const navigate = useNavigate()
  const mode = location.pathname.startsWith('/new/agent') ? 'agent' : 'hitl'

  return (
    <div className="mode-toggle" role="tablist" aria-label="Search mode">
      <button
        type="button"
        role="tab"
        aria-selected={mode === 'hitl'}
        className={mode === 'hitl' ? 'active' : ''}
        onClick={() => navigate('/new/hitl')}
      >
        Human-in-the-loop
      </button>
      <button
        type="button"
        role="tab"
        aria-selected={mode === 'agent'}
        className={mode === 'agent' ? 'active' : ''}
        onClick={() => navigate('/new/agent')}
      >
        Agent
      </button>
    </div>
  )
}
