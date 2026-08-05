import { useProjects } from '../context/ProjectsContext.jsx'
import EmptyState from './EmptyState.jsx'

export default function EmbeddingRunSelect({ value, onChange }) {
  const { embeddingRuns, embeddingRunsLoading, embeddingRunsError } = useProjects()

  if (embeddingRunsLoading) return <p className="field-status">Loading embedding runs…</p>
  if (embeddingRunsError) return <p className="field-status error">{embeddingRunsError}</p>
  if (embeddingRuns.length === 0) {
    return (
      <EmptyState
        title="No embedding runs found"
        description="The embedding pipeline hasn't been run yet — there's nothing to search against."
      />
    )
  }

  return (
    <select
      className="embedding-run-select"
      value={value ?? ''}
      onChange={(e) => onChange(Number(e.target.value))}
    >
      <option value="" disabled>
        Select an embedding run…
      </option>
      {embeddingRuns.map((run) => (
        <option key={run.run_id} value={run.run_id}>
          {run.embedding_model} · {run.n_dim}d · {new Date(run.ran_at).toLocaleString()}
        </option>
      ))}
    </select>
  )
}
