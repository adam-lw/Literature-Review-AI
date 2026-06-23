from papery.core.components.models import ContextModel
from papery.core.llm.core import get_llm
from pydantic import BaseModel, ConfigDict


# Parser prompt

parser_prompt = """
# Task description
You are a vector search query generator. You will be provided with a user prompt, and you will generate a vector search
query based on this user prompt. You will return the user prompt, along with additional information specified below,
in JSON format. Return the plain JSON string without a code block and without any additional input.

# Expected output format
{
    relevance: {
        rating: bool
        reason: str
    }
    query: str
    dates: tuple[int, int]
}

# Output Description
{
Key: "relevance"
{
Key: "rating": bool
Details: A boolean stating whether the user's query is feasibly relevant to an academic research question
Returns: true if the query is relevant, false if it's irrelevant, false if no user query has been provided
Examples: 
"What is 12*7" returns false because maths questions are not research related.
"Origins of COVID-19" returns true because this is a valid research question
---
Key: "reason", str
Details: Reason for your output for `rating`.
}
Key: "query": str
Details: If relevance.output is false, return null, otherwise:
You should convert the user's query into a string which is appropriate for a vector search across the embeddings
of research papers. Therefore, the returned string for `query` should have the following properties:
- There should be minimal filler, the search query should be to the point and precise.
- You should not omit details from the user's query unless they aren't useful in a vector search.
- query should be concise, no longer than 25 words.
- query should not contain years, dates, authors or specific journals.
- query should not contain additional user requests, such as details on output format.
Keep in mind that you will use query to perform a vector search, so think carefully.
---
Key: "dates": tuple[int, int]
Details: If the user has NOT explicitly provided any dates in their prompt, return null for this key. If they have provided a date range,
provide the lower and upper bounds of their search range as a tuple. The range is inclusive, so queries like "before 2020" should have an upper bound of 2019.
}

# User query:

"""


class Relevance(BaseModel):
    model_config = ConfigDict(strict=True)
    rating: bool
    reason: str


class SearchPayload(BaseModel):
    model_config = ConfigDict(strict=True)
    relevance: Relevance
    query: str | None
    dates: tuple[int | None, int | None] | None


llm = get_llm("gpt-4o-mini", parser=SearchPayload)

cm = ContextModel(llm=llm, system_prompt=parser_prompt)
print(
    cm.prompt(
        "Write me a research paper about convolutional neural networks as applied to petri dish classification. "
        "Include whether or not they were successful. Limit search to papers before 2020."
    )
)


agent_descriptor_prompt = """
# Task description
Below is the system prompt for a conversational agent. The agent is part of a multi-agent system. It is your job
to produce a concise summary of what the agent is doing.

You should output a bulleted list containing:
- A high-level summary of what the agent does based on its system prompt.
- A plaintext summary of the agent's inputs and outputs
- The parts of this agent's outputs which should be validated. Include full, precise details for this point.

Do not return anything else outside of the bulleted list.

# System prompt to evaluate
"""

cm = ContextModel(llm=get_llm(model="claude-3-5-haiku-20241022"))
print(cm.prompt(agent_descriptor_prompt + parser_prompt))
