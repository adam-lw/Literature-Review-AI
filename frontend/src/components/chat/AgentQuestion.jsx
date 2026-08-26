import { useState } from 'react'

// Renders a backend `Question` (an agent's `ask_user` call: status "awaiting_input") - its
// suggested options as pickable pills, plus a freetext field when the question allows one or
// has no options at all. Picking an option or submitting freetext both just answer with plain
// text, same as a regular chat message - the backend doesn't track option ids across the call.
export default function AgentQuestion({ question, onAnswer, disabled = false }) {
  const [freetext, setFreetext] = useState('')
  const { question: text, description, options, allows_freetext: allowsFreetext } = question
  const hasOptions = options && Object.keys(options).length > 0

  const submitFreetext = (e) => {
    e.preventDefault()
    const trimmed = freetext.trim()
    if (!trimmed || disabled) return
    setFreetext('')
    onAnswer(trimmed)
  }

  return (
    <div className="agent-question">
      <span className="chat-turn-label">Agent's question</span>
      <p>{text}</p>
      {description && <p className="agent-question-description">{description}</p>}

      {hasOptions && (
        <div className="pill-radio-group">
          {Object.entries(options).map(([key, label]) => (
            <button
              key={key}
              type="button"
              className="pill-radio"
              disabled={disabled}
              onClick={() => onAnswer(label)}
            >
              {label}
            </button>
          ))}
        </div>
      )}

      {(allowsFreetext || !hasOptions) && (
        <form className="agent-question-freetext" onSubmit={submitFreetext}>
          <input
            type="text"
            placeholder="Type your answer…"
            value={freetext}
            onChange={(e) => setFreetext(e.target.value)}
            disabled={disabled}
          />
          <button type="submit" disabled={disabled || !freetext.trim()}>
            Send
          </button>
        </form>
      )}
    </div>
  )
}
