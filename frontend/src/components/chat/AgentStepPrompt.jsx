export default function AgentStepPrompt({ description, onConfirm }) {
  return (
    <div className="agent-step-prompt">
      <span className="chat-turn-label">Agent's next step</span>
      <p>{description}</p>
      <button type="button" className="submit-btn" onClick={onConfirm}>
        Confirm
      </button>
    </div>
  )
}
