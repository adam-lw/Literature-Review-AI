import { useEffect, useState } from 'react'

const MAX_ROWS = 20

export default function QueryListInput({ onChange }) {
  const [rows, setRows] = useState([''])

  useEffect(() => {
    onChange(rows)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rows])

  const updateRow = (index, value) => {
    setRows((prev) => {
      const next = [...prev]
      const wasEmpty = next[index] === ''
      next[index] = value
      const isLast = index === next.length - 1
      if (isLast && wasEmpty && value !== '' && next.length < MAX_ROWS) {
        next.push('')
      }
      return next
    })
  }

  const removeRow = (index) => {
    setRows((prev) => prev.filter((_, i) => i !== index))
  }

  return (
    <div className="query-list-input">
      {rows.map((value, index) => (
        <div className="query-row" key={index}>
          <input
            type="text"
            value={value}
            placeholder={`Search term ${index + 1}`}
            onChange={(e) => updateRow(index, e.target.value)}
          />
          {index > 0 && (
            <button
              type="button"
              className="remove-row-btn"
              aria-label="Remove search term"
              onClick={() => removeRow(index)}
            >
              ×
            </button>
          )}
        </div>
      ))}
    </div>
  )
}
