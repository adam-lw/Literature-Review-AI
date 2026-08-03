
*Literature AI* is an agent-powered tool for the automated writing of literature review, meta-analysis and systematic review papers. 

The project was started with two goals: to be able to replicate existing literature review papers, and to produce new literature reviews from scratch. Manually producing these papers is typically repetitive and time-intensive, diverting researchers' time and effort away from potentially more productive activities in their research. Therefore, this project aims to automate, or significantly accelerate, this task.

The tool leverages a hybrid keyword & semantic search for paper retrieval, AI-as-a-Judge & heuristic-based ranking for paper selection, and an agent-driven architecture for paper writing & assessment. The codebase is designed to be deployable in Docker/Kubernetes and will provide an API via FastAPI.

Particular care has been taken to ensure that results are accurate and reproducable. Effective evaluation and observability measures are essential in ensuring that users trust the outputs of the tool, especially given AI's known ability to "hallucinate" and produce inconsistent outputs. A combination of quantitative and qualitative evaluation approaches have been selected, including precision and recall for paper retrieval against benchmark papers, perplexity for textual outputs, AI-as-a-Judge assessment, and manual human review.

The project is currently WIP.