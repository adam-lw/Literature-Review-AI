export default function AgentContinueBar({ showContinue = true, onContinue, onChat }) {
  return (
    <div className="agent-continue-bar">
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
  )
}
