import { useState } from 'react'

// Collapsed-by-default disclosure for the reasoning text an agent produced alongside a tool
// call this turn (`InvokeAgentResponse.reasoning`) - reuses the `.chevron`/`.chevron.open`
// rotate pattern already used for expanding paper abstracts in `PaperCard.jsx`.
export default function AgentThoughts({ text }) {
  const [expanded, setExpanded] = useState(false)
  if (!text) return null

  return (
    <div className="agent-thoughts">
      <button
        type="button"
        className="agent-thoughts-toggle"
        onClick={() => setExpanded((v) => !v)}
      >
        <span className={`chevron ${expanded ? 'open' : ''}`}>›</span>
        Thoughts
      </button>
      {expanded && <p className="agent-thoughts-body">{text}</p>}
    </div>
  )
}
