import { useState } from 'react'

// Time to let the `.agent-question-closing` CSS transition play before the answer is actually
// handed to the caller - keep in sync with the transition duration in global.css.
const CLOSE_ANIM_MS = 200

// Renders a backend `Question` (an agent's `ask_user` call: status "awaiting_input") - its
// suggested options as pickable pills, plus a freetext field when the question allows one or
// has no options at all. Picking an option or submitting freetext both just answer with plain
// text, same as a regular chat message - the backend doesn't track option ids across the call.
//
// Answering collapses this card in place before `onAnswer` fires, so the parent (which swaps
// this card out for a "Thinking…" placeholder once `onAnswer` triggers the next agent call) only
// does so after the collapse has actually played.
export default function AgentQuestion({ question, onAnswer, disabled = false }) {
  const [freetext, setFreetext] = useState('')
  const [closing, setClosing] = useState(false)
  const { question: text, description, options, allows_freetext: allowsFreetext } = question
  const hasOptions = options && Object.keys(options).length > 0

  const answer = (value) => {
    if (closing || disabled) return
    setClosing(true)
    setTimeout(() => onAnswer(value), CLOSE_ANIM_MS)
  }

  const submitFreetext = (e) => {
    e.preventDefault()
    const trimmed = freetext.trim()
    if (!trimmed) return
    setFreetext('')
    answer(trimmed)
  }

  return (
    <div className={`agent-question ${closing ? 'agent-question-closing' : ''}`}>
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
              disabled={disabled || closing}
              onClick={() => answer(label)}
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
            disabled={disabled || closing}
          />
          <button type="submit" disabled={disabled || closing || !freetext.trim()}>
            Send
          </button>
        </form>
      )}
    </div>
  )
}
