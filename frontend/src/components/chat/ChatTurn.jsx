export default function ChatTurn({ role = 'assistant', wide = false, label, children }) {
  return (
    <div className={`chat-turn chat-turn-${role}`}>
      {label && <div className="chat-turn-label">{label}</div>}
      <div className={`chat-bubble chat-bubble-${role} ${wide ? 'wide' : ''}`}>{children}</div>
    </div>
  )
}
