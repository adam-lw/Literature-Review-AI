# Deriving Method Review Search Terms via Minimised Paper Cosine Similarity Metrics

Idea:
- Take a cohort of method review papers.
- Note the search terms used in each paper, and generate a list of additional potential search terms via LLM.
- For each search term, take the cosine distance between every paper in the cohort.
- Rank each search term:
  - Minimise overall cosine distance
  - But factoring in the number of similar, non-relevant papers. Generic search terms get punished.
- Best ranking search terms get used to fine tune an LLM.
- Compare naive LLM performance for generating search terms based on a topic + description under varying prompt engineering regimes, versus a fine tuned approach