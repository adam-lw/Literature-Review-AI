# Evaluation Design
This document is concerned with the design decisions made to allow the proper evaluation of the Papery AI application.

Evaluation is essential to assess the performance of the application in relation to its stated objectives. For Papery, this can be broken into several steps:

## Retrieval Assessment
The first step in producing a systematic review is to perform a literature search. Evaluating retrieval systems has been a longstanding area of research long before the popularisation of AI applications, with metrics such as clickthrough rate and dwell time used to assess the human-rated functional usefulness of results. However, these metrics are not appropriate here.

Possible evaluation metrics/methods:
- AI as a Judge - for each retrieved research paper, use an AI to score a paper's relevance to the user's query and context provided by the system prompt.
- Ranking - papers are ranked by an AI based on their deemed relevance to the query against each other. 
- Human review - for a given query, evaluate an AI's results against a human-selected set of papers (slow, expensive, time consuming, boring, potential for errors)
- Comparison to existing systematic reviews - does the AI correctly find the referenced papers?
- User selection - allow the user to optionally review and select/de-select the outputted papers discovered for a literature search, along with a brief AI-generated description of each paper and why it's relevant.
  - Allows us to assess overall application performance - a lower number of paper removals is good.
  - Very noisy signal, users may not properly read papers, it's a poor metric.
  - Selection of papers deemed to be irrelevant by the AI is a useful signal.

Considerations
- Paper recency - we want to select newer papers, not older papers

### Subpoint - AI Summary Assessment
- Evaluate whether the generated summaries for each paper, and why they're relevant, are factually accurate.
- AI as a judge (alignment)


## Generation Assessment

- Does the AI meet the proper tonality, formatting, structure and pacing of the desired output?
- 