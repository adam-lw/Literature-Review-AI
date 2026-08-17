export default function PlaceholderNotice({ feature, detail }) {
  return (
    <div className="placeholder-notice">
      <span className="placeholder-notice-badge">Not yet implemented</span>
      <p>
        <strong>{feature}</strong> isn't wired up to the backend yet. {detail}
      </p>
    </div>
  )
}
