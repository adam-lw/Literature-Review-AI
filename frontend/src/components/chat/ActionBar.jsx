const ACTIONS = [
  {
    key: 'summary',
    label: 'Generate summary',
    description: 'Summarise the collected papers',
  },
  {
    key: 'lit-review',
    label: 'Write literature review',
    description: 'Full draft in your chosen format — invokes the writing agent',
  },
  {
    key: 'gaps',
    label: 'Find research gaps',
    description: "Surface what the collected papers don't cover",
  },
  {
    key: 'chat',
    label: 'Chat with AI',
    description: 'Ask questions about the findings',
  },
]

export default function ActionBar({ onAction, disabled = false }) {
  return (
    <div className="action-bar">
      {ACTIONS.map((action) => (
        <button
          key={action.key}
          type="button"
          className="action-bar-btn"
          disabled={disabled}
          onClick={() => onAction(action.key)}
        >
          <span className="action-bar-btn-label">{action.label}</span>
          <span className="action-bar-btn-desc">{action.description}</span>
        </button>
      ))}
    </div>
  )
}
