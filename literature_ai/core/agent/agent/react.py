from loguru import logger

from literature_ai.core.agent.llm.core import LLM
from literature_ai.core.agent.llm.messages import Message, Messages, MessageLike
from literature_ai.core.agent.llm.tool_call import ToolCall
from literature_ai.core.agent.memory import MemoryObject, get_formatted_memory
from literature_ai.core.agent.tools import Tool
from typing import Any, Optional
from literature_ai.core.agent.prompt.prompt import get_prompt
from literature_ai.core.agent.tools.skills import get_formatted_skills


def _truncate(value: Any, limit: int = 300) -> str:
    text = str(value)
    return text if len(text) <= limit else text[:limit] + "…"


class Agent:
    def __init__(
        self,
        instructions: MessageLike,
        llm: LLM,
        tools: list[Tool],
        memory: Optional[dict[str, MemoryObject]] = None,
    ):
        self.llm = llm
        self.tools = {t.name: t for t in tools}
        self.memory = memory or {}

        agent_prompt = get_prompt("react")
        skills = get_formatted_skills()
        memory_summary = get_formatted_memory(self.memory)
        self.context = Messages([agent_prompt + skills + memory_summary, instructions])

        logger.debug(f"Agent initialised: tools={list(self.tools)} memory={list(self.memory)}")

    async def run_agent(
        self,
        *,
        task: Optional[str] = None,
        max_iter: int = 5,
    ) -> str:
        # Append task to instructions message if provided
        if task:
            self.context[0] = Message(
                role=self.context[0].role,
                content=self.context[0].content + task,
            )

        for iteration in range(1, max_iter + 1):
            logger.debug(f"Iteration {iteration}/{max_iter}: calling LLM ({type(self.llm).__name__})")
            result = await self.llm.call(self.context, tools=list(self.tools.values()))

            if isinstance(result, str):
                logger.debug(f"LLM returned final response: {_truncate(result)}")
                self.context.add(result, role="assistant")
                return result

            # Handle tool calls in result
            logger.debug(f"LLM requested {len(result)} tool call(s): {[tc.name for tc in result]}")
            for tool_call in result:
                self.context.add(
                    f"Called tool `{tool_call.name}` with arguments {tool_call.arguments}",
                    role="assistant",
                )

                if tool_call.name not in self.tools:
                    logger.debug(f"Tool `{tool_call.name}` is not registered")
                    self.context.add(
                        f"Error: tool `{tool_call.name}` is not available. "
                        f"Available tools: {', '.join(self.tools) or 'none'}.",
                        role="tool",
                    )
                    continue

                tool_result = self._call_tool(tool_call)
                logger.debug(f"Tool `{tool_call.name}` -> {_truncate(tool_result)}")
                self.context.add(str(tool_result), role="tool")

        logger.debug(f"Agent did not converge within {max_iter} iterations")
        raise RuntimeError(f"Agent did not converge within {max_iter} iterations.")

    def _call_tool(self, tool_call: ToolCall) -> Any:
        tool = self.tools[tool_call.name]
        kwargs = dict(tool_call.arguments)

        if tool.accepts_memory:
            memory_object = next(
                (
                    obj
                    for obj in self.memory.values()
                    if tool.memory_type is None or isinstance(obj, tool.memory_type)
                ),
                None,
            )

            if memory_object is None:
                expected = tool.memory_type.__name__ if tool.memory_type else "any"
                logger.debug(f"No `{expected}` memory available for tool `{tool.name}`")
                return f"Error: no `{expected}` memory is available for tool `{tool.name}`."

            logger.debug(f"Injecting {type(memory_object).__name__} into tool `{tool.name}`")
            kwargs["memory"] = memory_object

        return tool.invoke(**kwargs)
