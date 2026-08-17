import SearchTermGroup from './SearchTermGroup.jsx'
import EmptyState from './EmptyState.jsx'

export default function ResultsPanel({
  searches,
  dedupeCounts,
  onToggleInclude,
  onSetAll,
  onRemoveTerm,
  agentAssessments,
  emptyTitle = 'No search terms yet',
  emptyDescription = 'Add a term above to start finding papers.',
}) {
  if (searches.length === 0) {
    return <EmptyState title={emptyTitle} description={emptyDescription} />
  }

  return (
    <div className="results-panel">
      {searches.map((search) => (
        <SearchTermGroup
          key={search.search_id}
          search={search}
          dedupeCounts={dedupeCounts}
          onToggleInclude={onToggleInclude}
          onSetAll={onSetAll}
          onRemoveTerm={onRemoveTerm}
          agentAssessments={agentAssessments?.[search.search_id]}
        />
      ))}
    </div>
  )
}
