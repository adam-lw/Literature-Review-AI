import { useState } from 'react'

export default function AgentLandingPage() {
  const [text, setText] = useState('')

  return (
    <div className="landing-page">
      <h1>Describe the search you'd like to undertake</h1>
      <form className="agent-form" onSubmit={(e) => e.preventDefault()}>
        <textarea
          className="agent-textarea"
          rows={8}
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Describe the search you'd like to undertake."
        />
        <button
          type="submit"
          className="submit-btn"
          disabled
          title="Agentic search is not yet implemented."
        >
          Submit
        </button>
      </form>
    </div>
  )
}
