// Shared helper for the scoping phase's JSON handoff artifact (see
// `config/core/agent/prompts/agent_types/scoping.md`'s "Required output" section): its sole
// completed-turn output is either plain conversational text, or - when it has just
// finalized/updated the specification - the entire turn is exactly one JSON object conforming to
// the scope schema. This distinguishes the two, so callers only update their locally stored scope
// on the latter.
export function tryParseScope(text) {
  if (typeof text !== 'string') return null

  let parsed
  try {
    parsed = JSON.parse(text)
  } catch {
    return null
  }

  if (parsed === null || typeof parsed !== 'object' || Array.isArray(parsed)) return null
  return parsed
}
