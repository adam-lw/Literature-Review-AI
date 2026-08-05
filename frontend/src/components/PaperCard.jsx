import { useState } from 'react'
import IncludeCheckbox from './IncludeCheckbox.jsx'

const METRIC_LABEL = { cosine: 'cos', l2: 'l2', ip: 'ip' }

export default function PaperCard({ result, onToggleInclude, alsoInTerms }) {
  const [expanded, setExpanded] = useState(false)
  const metricLabel = METRIC_LABEL[result.distance_type] || result.distance_type || 'dist'

  return (
    <li className={`paper-card ${result.included ? '' : 'excluded'}`}>
      <div className="paper-card-row" onClick={() => setExpanded((v) => !v)}>
        <IncludeCheckbox checked={result.included} onChange={(v) => onToggleInclude(result.result_id, v)} />
        <div className="paper-card-main">
          <div className="paper-title-row">
            <span className="paper-title">{result.title || 'Untitled'}</span>
            {alsoInTerms > 0 && <span className="also-in-badge">also in {alsoInTerms} terms</span>}
          </div>
          <div className="paper-meta">
            {result.year ?? '—'} · {result.venue || '—'} · {result.citation_count ?? 0} citations ·{' '}
            {metricLabel} {result.distance != null ? result.distance.toFixed(2) : '—'}
          </div>
        </div>
        <button
          type="button"
          className={`chevron ${expanded ? 'open' : ''}`}
          aria-label={expanded ? 'Collapse abstract' : 'Expand abstract'}
          onClick={(e) => {
            e.stopPropagation()
            setExpanded((v) => !v)
          }}
        >
          ›
        </button>
      </div>

      {expanded && (
        <div className="paper-card-details">
          <p className="paper-abstract">{result.abstract || 'No abstract available.'}</p>
          <div className="paper-links">
            <a
              className={`pdf-link ${!result.url ? 'disabled' : ''}`}
              href={result.url || undefined}
              target="_blank"
              rel="noreferrer"
              title={result.url ? undefined : 'No open-access PDF available'}
              onClick={(e) => {
                if (!result.url) e.preventDefault()
              }}
            >
              PDF ↗
            </a>
            {result.doi && (
              <a className="doi-link" href={`https://doi.org/${result.doi}`} target="_blank" rel="noreferrer">
                DOI: {result.doi}
              </a>
            )}
          </div>
        </div>
      )}
    </li>
  )
}
