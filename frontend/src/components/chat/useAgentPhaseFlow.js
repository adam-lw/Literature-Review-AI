import { useEffect, useState } from 'react'

// The fixed sequence the agent proposes, whether a project started in Agent mode or was
// switched into it mid-project. Each step is proposed and must be confirmed before its
// result is added to the log; after the result appears, the flow stops for a Continue/Chat
// choice rather than chaining straight through to the end.
export const AGENT_STEPS = [
  {
    key: 'search-terms',
    description: 'Derive search terms from the description and criteria, then run them automatically.',
    kind: 'notice',
    feature: 'Automatic search-term generation',
    detail:
      'Once implemented, the agent will derive search terms from the project description and criteria and run them automatically.',
  },
  {
    key: 'evaluate',
    description: 'Collect candidate papers and evaluate each one against the inclusion criteria.',
    kind: 'evaluate',
  },
  {
    key: 'formatting',
    description: 'Decide how the literature review should be formatted.',
    kind: 'questionnaire',
  },
  {
    key: 'writing',
    description: 'Write the full literature review in the chosen format.',
    kind: 'notice',
    feature: 'Literature review writing',
  },
]

export function useAgentStepFlow(active) {
  const [stepIndex, setStepIndex] = useState(0)
  const [phase, setPhase] = useState('confirm') // 'confirm' | 'continue' | 'done'

  // Every time this project (re-)enters Agent mode, start from the first proposed step.
  useEffect(() => {
    if (active) {
      setStepIndex(0)
      setPhase('confirm')
    }
  }, [active])

  const confirm = () => {
    setPhase(stepIndex >= AGENT_STEPS.length - 1 ? 'done' : 'continue')
  }

  const continueNext = () => {
    setStepIndex((i) => i + 1)
    setPhase('confirm')
  }

  return {
    step: AGENT_STEPS[stepIndex],
    stepIndex,
    phase,
    confirm,
    continueNext,
  }
}
