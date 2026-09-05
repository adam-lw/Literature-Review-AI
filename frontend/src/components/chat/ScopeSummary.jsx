import { useState } from 'react'

// Renders the scoping agent's finalized JSON specification (schema documented in
// `config/core/agent/prompts/agent_types/scoping.md`) as a human-readable summary instead of
// dumping the raw JSON into the chat transcript. The spec is an untyped dict end-to-end (no
// server-side schema validation - see `ScopingMemoryObject`), so every access here is defensive.

function Section({ title, children }) {
  return (
    <div className="scope-section">
      <h4 className="scope-section-title">{title}</h4>
      {children}
    </div>
  )
}

function Field({ label, value }) {
  if (value === undefined || value === null || value === '') return null
  return (
    <div className="scope-field">
      <span className="scope-field-label">{label}</span>
      <span className="scope-field-value">{value}</span>
    </div>
  )
}

function ChipGroup({ label, items }) {
  if (!items || items.length === 0) return null
  return (
    <div className="scope-field">
      <span className="scope-field-label">{label}</span>
      <div className="scope-chip-row">
        {items.map((item) => (
          <span key={item} className="scope-chip">
            {item}
          </span>
        ))}
      </div>
    </div>
  )
}

export default function ScopeSummary({ specification }) {
  const [showRaw, setShowRaw] = useState(false)
  const spec = specification || {}
  const review = spec.review_definition || {}
  const timeWindow = review.time_window || {}
  const criteria = spec.inclusion_exclusion_criteria || {}
  const topical = spec.topical_relevance || {}
  const termMap = topical.term_map || {}
  const borderlineCases = topical.resolved_borderline_cases || []
  const openItems = spec.open_items || []

  return (
    <div className="scope-summary">
      <div className="scope-summary-header">
        <span className="scope-summary-badge">Scope confirmed</span>
      </div>

      {spec.research_questions?.length > 0 && (
        <Section title="Research questions">
          <ul className="scope-list">
            {spec.research_questions.map((q) => (
              <li key={q}>{q}</li>
            ))}
          </ul>
        </Section>
      )}

      <Section title="Review definition">
        <Field label="Object of review" value={review.object_of_review} />
        <Field label="Granularity" value={review.granularity} />
        <Field
          label="Time window"
          value={
            timeWindow.start &&
            `${timeWindow.start}${timeWindow.rationale ? ` — ${timeWindow.rationale}` : ''}`
          }
        />
        <Field label="Search cutoff date" value={timeWindow.search_cutoff_date} />
        <Field label="Domain bounds" value={review.domain_bounds} />
        <ChipGroup label="Publication types" items={review.publication_types_included} />
        <Field label="Rigor level" value={review.rigor_level} />
      </Section>

      <Section title="Inclusion / exclusion criteria">
        <ChipGroup label="Methodological focus" items={criteria.methodological_focus} />
        <Field
          label="Application context restrictions"
          value={criteria.application_context_restrictions ?? 'None'}
        />
        <Field label="Comparator requirement" value={criteria.comparator_requirement ?? 'Not required'} />
        <Field label="Minimum reporting bar" value={criteria.minimum_reporting_bar} />
        <ChipGroup label="Study types included" items={criteria.study_types_included} />
        <Field label="Language" value={criteria.language_restriction} />
        <Field
          label="Full text required"
          value={
            criteria.full_text_access_required === undefined
              ? undefined
              : criteria.full_text_access_required
                ? 'Yes'
                : 'No'
          }
        />
        <Field label="Duplicate / version handling" value={criteria.duplicate_version_handling} />
      </Section>

      <Section title="Topical relevance">
        <Field label="Definition" value={topical.operational_definition} />
        <ChipGroup label="Core terms" items={termMap.core_terms} />
        <ChipGroup label="Synonyms & aliases" items={termMap.synonyms_and_aliases} />
        <ChipGroup label="Excluded lookalike terms" items={termMap.excluded_lookalike_terms} />
        {borderlineCases.length > 0 && (
          <div className="scope-field">
            <span className="scope-field-label">Resolved borderline cases</span>
            <ul className="scope-list">
              {borderlineCases.map((c) => (
                <li key={c.case_description}>
                  <strong>{c.case_description}</strong> — {c.decision}
                  {c.reasoning && `: ${c.reasoning}`}
                </li>
              ))}
            </ul>
          </div>
        )}
      </Section>

      {spec.search_terms?.length > 0 && (
        <Section title="Search terms">
          <div className="scope-chip-row">
            {spec.search_terms.map((term) => (
              <span key={term} className="scope-chip">
                {term}
              </span>
            ))}
          </div>
        </Section>
      )}

      {openItems.length > 0 && (
        <div className="scope-callout scope-callout-warning">
          <span className="scope-callout-title">Open items</span>
          <ul className="scope-list">
            {openItems.map((item) => (
              <li key={item.field}>
                <strong>{item.field}</strong>: {item.reason}
              </li>
            ))}
          </ul>
        </div>
      )}

      {spec.scope_risk_note && (
        <div className="scope-callout">
          <span className="scope-callout-title">Scope risk note</span>
          <p>{spec.scope_risk_note}</p>
        </div>
      )}

      <button type="button" className="agent-thoughts-toggle" onClick={() => setShowRaw((v) => !v)}>
        <span className={`chevron ${showRaw ? 'open' : ''}`}>›</span>
        View raw JSON
      </button>
      {showRaw && <pre className="scope-raw-json">{JSON.stringify(specification, null, 2)}</pre>}
    </div>
  )
}
