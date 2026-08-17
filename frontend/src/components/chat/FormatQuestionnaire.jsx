import { useState } from 'react'

const CITATION_STYLES = ['IEEE', 'APA', 'MLA', 'Chicago', 'Harvard']
const SECTIONS = [
  'Abstract',
  'Introduction',
  'Methodology',
  'Thematic synthesis',
  'Research gaps',
  'Conclusion',
  'Reference list',
]

export default function FormatQuestionnaire({ onSubmit, submitLabel = 'Start writing' }) {
  const [citationStyle, setCitationStyle] = useState('IEEE')
  const [sections, setSections] = useState(() => new Set(['Abstract', 'Introduction', 'Conclusion', 'Reference list']))

  const toggleSection = (section) => {
    setSections((prev) => {
      const next = new Set(prev)
      if (next.has(section)) next.delete(section)
      else next.add(section)
      return next
    })
  }

  const handleSubmit = (e) => {
    e.preventDefault()
    onSubmit({ citationStyle, sections: SECTIONS.filter((s) => sections.has(s)) })
  }

  return (
    <form className="format-questionnaire" onSubmit={handleSubmit}>
      <div className="format-questionnaire-group">
        <span className="field-label">Citation format</span>
        <div className="pill-radio-group">
          {CITATION_STYLES.map((style) => (
            <label key={style} className={`pill-radio ${citationStyle === style ? 'selected' : ''}`}>
              <input
                type="radio"
                name="citation-style"
                value={style}
                checked={citationStyle === style}
                onChange={() => setCitationStyle(style)}
              />
              {style}
            </label>
          ))}
        </div>
      </div>

      <div className="format-questionnaire-group">
        <span className="field-label">Sections to include</span>
        <div className="checkbox-grid">
          {SECTIONS.map((section) => (
            <label key={section} className="checkbox-tile">
              <input
                type="checkbox"
                checked={sections.has(section)}
                onChange={() => toggleSection(section)}
              />
              {section}
            </label>
          ))}
        </div>
      </div>

      <button type="submit" className="submit-btn" disabled={sections.size === 0}>
        {submitLabel}
      </button>
    </form>
  )
}
