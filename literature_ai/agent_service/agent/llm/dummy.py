from typing import Optional, Union

from literature_ai.agent_service.agent.llm.core import LLM, Messages
from literature_ai.agent_service.agent.tools import Tool, ToolCall


class DummyLLM(LLM):
    """
    Canned LLM for local/dev use - never calls out to a real provider.

    Always returns a fixed text reply echoing the last message it was given,
    so the agent loop (and everything downstream of it, like the
    create_agent/invoke_agent API) can be exercised without API keys,
    network access, or cost.
    """

    def __init__(self, model: str = "dummy"):
        self.model = model

    def format_tools(self, tools: list[Tool]) -> list[str]:
        return [t.name for t in tools]

    async def call(
        self, messages: Messages, tools: Optional[list[Tool]] = None
    ) -> Union[str, list[ToolCall]]:
        last = messages[-1] if len(messages) else None
        return f"[dummy] {last.content if last else ''}"
