export default function CriteriaEditor({ value, onChange, onBlur }) {
  return (
    <textarea
      className="criteria-editor"
      placeholder="Inclusion / exclusion criteria (optional)…"
      value={value ?? ''}
      onChange={(e) => onChange(e.target.value)}
      onBlur={onBlur}
      rows={4}
    />
  )
}
