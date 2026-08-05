import { useState } from 'react'
import PaperCard from './PaperCard.jsx'

export default function SearchTermGroup({ search, dedupeCounts, onToggleInclude, onSetAll, onRemoveTerm }) {
  const [collapsed, setCollapsed] = useState(false)
  const includedCount = search.results.filter((r) => r.included).length

  return (
    <section className="search-term-group">
      <header className="search-term-header" onClick={() => setCollapsed((v) => !v)}>
        <button
          type="button"
          className={`chevron ${collapsed ? '' : 'open'}`}
          aria-label={collapsed ? 'Expand group' : 'Collapse group'}
        >
          ›
        </button>
        <span className="search-term-query">{search.query}</span>
        <span className="search-term-counts">
          {search.results.length} results · {includedCount} included
        </span>
        <div className="search-term-actions" onClick={(e) => e.stopPropagation()}>
          <button type="button" onClick={() => onSetAll(search.search_id, true)}>
            Select all
          </button>
          <button type="button" onClick={() => onSetAll(search.search_id, false)}>
            Select none
          </button>
          <button type="button" className="remove-term-btn" onClick={() => onRemoveTerm(search.search_id)}>
            Remove term
          </button>
        </div>
      </header>

      {!collapsed && (
        <ul className="paper-card-list">
          {search.results.map((result) => (
            <PaperCard
              key={result.result_id}
              result={result}
              onToggleInclude={onToggleInclude}
              alsoInTerms={(dedupeCounts[result.paper_id] || 1) - 1}
            />
          ))}
          {search.results.length === 0 && <li className="empty-group">No results for this term.</li>}
        </ul>
      )}
    </section>
  )
}
