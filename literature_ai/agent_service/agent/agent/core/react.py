from loguru import logger
from langfuse import get_client

from literature_ai.agent_service.agent.agent.core.response import (
    AgentResponse,
    Question,
)
from literature_ai.agent_service.agent.llm.core import (
    LLM,
    Message,
    Messages,
    MessageLike,
)
from literature_ai.agent_service.agent.memory import MemoryObject
from literature_ai.agent_service.agent.tools import Tool, ToolCall
from typing import Any, Optional
from literature_ai.agent_service.agent.tools.tools.agent_util_tools import ASK_USER_TOOL


class ReactAgent:
    def __init__(
        self,
        system_prompt: str,
        llm: LLM,
        tools: list[Tool],
        memory: Optional[dict[str, MemoryObject]] = None,
        allow_questions: bool = False,
    ):
        self.llm = llm
        self.tools = {t.name: t for t in tools}

        # Insert question asking tool if requested
        if allow_questions:
            self.tools[ASK_USER_TOOL.name] = ASK_USER_TOOL

        self.memory = memory or {}

        self.context = Messages([{"system": system_prompt}])

        logger.debug(
            f"Agent initialised: tools={list(self.tools)} memory={list(self.memory)}"
        )

    async def run_agent(
        self,
        *,
        content: Optional[MessageLike] = None,
        max_iter: int = 5,
    ) -> AgentResponse:
        # A plain string is attributed to the user; a `Message`/dict/`Messages`
        # is appended as-is, so multi-turn history (e.g. from `resume_agent`)
        # replays into the context with its original roles intact.
        if content:
            if isinstance(content, str):
                self.context.add_user(content)
            else:
                self.context.append(content)

        # Text a model emits alongside a tool call within this `run_agent` call is reasoning,
        # not a final answer (see `LLMResponse`'s docstring) - collected here so callers can
        # show it separately from the turn's actual result.
        reasoning_parts: list[str] = []

        try:
            for iteration in range(1, max_iter + 1):
                # Reason
                result = await self.llm.call(
                    self.context, tools=list(self.tools.values())
                )

                if result.content:
                    self.context.add(result.content, role="assistant")

                if not result.tool_calls:
                    return AgentResponse(
                        status="completed",
                        state=self.context,
                        result=Message(
                            role="assistant", content=result.content or ""
                        ),
                        reasoning="\n\n".join(reasoning_parts) or None,
                    )

                if result.content:
                    reasoning_parts.append(result.content)

                # Handle tool calls in result
                logger.debug(
                    f"LLM requested {len(result.tool_calls)} tool call(s): "
                    f"{[tc.name for tc in result.tool_calls]}"
                )
                for tool_call in result.tool_calls:
                    self.context.add(
                        f"Called tool `{tool_call.name}` with arguments {tool_call.arguments}",
                        role="assistant",
                    )

                    if tool_call.name == ASK_USER_TOOL.name:
                        question = Question(
                            question=tool_call.arguments["question"],
                            description=tool_call.arguments.get("description", ""),
                            options=tool_call.arguments.get("options") or {},
                            allows_freetext=tool_call.arguments.get(
                                "allows_freetext", True
                            ),
                        )
                        return AgentResponse(
                            status="awaiting_input",
                            state=self.context,
                            result=question,
                            reasoning="\n\n".join(reasoning_parts) or None,
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
                    self.context.add(str(tool_result), role="tool")

            logger.debug(f"Agent did not converge within {max_iter} iterations")
            return AgentResponse(
                status="error",
                state=self.context,
                result=Message(
                    role="assistant",
                    content=f"Agent did not converge within {max_iter} iterations.",
                ),
                reasoning="\n\n".join(reasoning_parts) or None,
            )
        except Exception as exc:
            logger.exception(f"Agent loop failed: {exc}")
            return AgentResponse(
                status="error",
                state=self.context,
                result=Message(role="assistant", content=str(exc)),
                reasoning="\n\n".join(reasoning_parts) or None,
            )

    def _call_tool(self, tool_call: ToolCall) -> Any:
        """
        Generic tool-invocation point every registry tool call passes through
        (`ask_user` is special-cased earlier in the loop and never reaches
        here). Reported to Langfuse as a "tool" observation nested under the
        current trace/span - see `LangfuseLLM` for the equivalent on the LLM
        side.
        """
        tool = self.tools[tool_call.name]
        kwargs = dict(tool_call.arguments)

        # ensure we log to langfuse
        client = get_client()
        with client.start_as_current_observation(
            as_type="tool",
            name=tool_call.name,
            input=tool_call.arguments,
            metadata={"tool_call_id": tool_call.id},
        ) as span:
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
                    logger.debug(
                        f"No `{expected}` memory available for tool `{tool.name}`"
                    )
                    result = f"Error: no `{expected}` memory is available for tool `{tool.name}`."
                    span.update(output=result, level="WARNING", status_message=result)
                    return result

                logger.debug(
                    f"Injecting {type(memory_object).__name__} into tool `{tool.name}`"
                )
                kwargs["memory"] = memory_object

            try:
                result = tool.invoke(**kwargs)
            except Exception as e:
                span.update(level="ERROR", status_message=str(e))
                raise

            span.update(output=result)
            return result
