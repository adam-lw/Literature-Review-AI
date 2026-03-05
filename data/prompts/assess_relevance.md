You are tasked with evaluating how relevant a research paper summary is to a specific user query.

You will be given:
- A user query describing a topic, question, or research need.
- A research paper summary outlining the paper’s objectives, methods, and findings.

Your goal is to assess the degree of relevance between the query and the summary.

Instructions:
- Determine whether the paper directly addresses the core intent of the user query, partially addresses it, or is unrelated.
- Focus on alignment of topic, research question, population (if applicable), methodology (if relevant), and outcomes.
- Consider both explicit matches (clearly stated overlap) and implicit matches (strong conceptual similarity even if terminology differs).
- Distinguish between surface-level keyword overlap and true conceptual relevance.
- If the summary is too vague to determine relevance, state that explicitly.

Output format:
- Relevance score: High / Moderate / Low / None
- Brief justification (2–4 sentences) explaining your reasoning, referencing specific aspects of both the query and the summary.
- Optional: A short note on what would be needed to increase confidence in the assessment (if uncertainty exists).

User Query:
{{ user_query }}

Research Paper Summary:
{{ paper_summary }}