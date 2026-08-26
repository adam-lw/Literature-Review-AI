from dataclasses import asdict
from typing import Any, Optional, Union

from langfuse import get_client

from literature_ai.agent_service.agent.llm.core import LLM, Messages
from literature_ai.agent_service.agent.tools import Tool, ToolCall


def _serialize_response(response: Union[str, list[ToolCall]]) -> Any:
    if isinstance(response, list):
        return [asdict(tc) for tc in response]
    return response


class LangfuseLLM(LLM):
    """
    Wrapper around an LLM class which reports each call to Langfuse as a
    generation observation, nested under whatever trace/span is currently
    active (see `@observe` on `invoke_agent`). Reporting is a no-op unless
    `LANGFUSE_PUBLIC_KEY`/`LANGFUSE_SECRET_KEY` are configured - the SDK
    disables itself safely when they're absent.
    """

    def __init__(self, llm: LLM):
        self._llm = llm

    def format_tools(self, tools: list[Tool]) -> Any:
        return self._llm.format_tools(tools)

    async def call(
        self, messages: Messages, tools: Optional[list[Tool]] = None
    ) -> Union[str, list[ToolCall]]:
        client = get_client()
        model = getattr(self._llm, "model", "unknown")

        with client.start_as_current_observation(
            as_type="generation",
            name="llm-call",
            model=model,
            input=messages.to_list(),
        ) as generation:
            try:
                response = await self._llm.call(messages, tools=tools)
            except Exception as e:
                generation.update(level="ERROR", status_message=str(e))
                raise
            generation.update(output=_serialize_response(response))
            return response
