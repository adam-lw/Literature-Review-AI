export default function AgentContinueBar({ showContinue = true, hint, onContinue, onChat }) {
  return (
    <div className="agent-continue-bar">
      {showContinue && hint && <p className="agent-continue-hint">{hint}</p>}
      <div className="agent-continue-actions">
        {showContinue ? (
          <button type="button" className="submit-btn" onClick={onContinue}>
            Continue
          </button>
        ) : (
          <span className="agent-continue-done">That was the last step.</span>
        )}
        <button type="button" className="chat-reveal-btn" onClick={onChat}>
          Chat with AI
        </button>
      </div>
    </div>
  )
}
