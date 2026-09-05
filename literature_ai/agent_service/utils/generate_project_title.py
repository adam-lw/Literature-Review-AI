from literature_ai.agent_service.agent.llm.core import Messages, get_llm
from literature_ai.agent_service.agent.prompt.prompt import get_prompt

MODEL = "gpt-5.6-luna"


async def generate_title(user_input: str) -> str:
    """
    Generates a short working title for a new literature review project from
    the user's initial description of it.
    """
    llm = get_llm(MODEL)

    messages = Messages([get_prompt("utils/generate_title")])
    messages.add_user(user_input)

    response = await llm.call(messages)

    return (response.content or "").strip()
