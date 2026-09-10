import json
from typing import Any

from literature_ai.agent_service.agent.llm.core import Messages, get_llm
from literature_ai.agent_service.agent.prompt.prompt import get_prompt

MODEL = "gpt-5.6-luna"


async def generate_scope_title(specification: dict[str, Any]) -> str:
    """
    Generates a short title for a finalized scoping specification, distinct from the
    project's own project_title.
    """
    llm = get_llm(MODEL)

    messages = Messages([get_prompt("utils/generate_scope_title")])
    messages.add_user(json.dumps(specification, indent=2))

    response = await llm.call(messages)

    return (response.content or "").strip()
