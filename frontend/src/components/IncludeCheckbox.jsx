export default function IncludeCheckbox({ checked, onChange, label = 'Include this paper' }) {
  return (
    <input
      type="checkbox"
      className="include-checkbox"
      checked={checked}
      onChange={(e) => onChange(e.target.checked)}
      aria-label={label}
      onClick={(e) => e.stopPropagation()}
    />
  )
}
