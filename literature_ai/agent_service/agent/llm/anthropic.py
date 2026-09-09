from literature_ai.agent_service.agent.llm.core import LLM, LLMResponse, Messages
from literature_ai.agent_service.agent.tools import Tool, ToolCall
from typing import Any, Optional, cast
from anthropic import AsyncAnthropic, omit
from anthropic.types import MessageParam, TextBlock, ToolParam, ToolUseBlock
import os

ANTHROPIC_MODELS = ["claude-haiku-4-5", "claude-sonnet-5", "claude-opus-5"]


class AnthropicLLM(LLM):
    def __init__(self, model: str, **config: Any):
        self._validate_model(model=model)
        self.model = model
        self.client = AsyncAnthropic(
            api_key=os.environ.get(
                "ANTHROPIC_API_KEY"
            ),  # This is the default and can be omitted
        )

    def _validate_model(self, model: str):
        """Validates that a legal Anthropic (Claude) model has been passed"""
        if model not in ANTHROPIC_MODELS:
            raise ValueError(
                f"{model} is not a legal Anthropic model. Available models: {ANTHROPIC_MODELS}"
            )

    def format_tools(self, tools: list[Tool]) -> list[ToolParam]:
        return [
            {
                "name": t.name,
                "description": t.description,
                "input_schema": {
                    "type": "object",
                    "properties": {
                        p["param_name"]: {
                            "type": p["type"],
                            "description": p["description"],
                        }
                        for p in t.params
                    },
                    "required": [p["param_name"] for p in t.params if p["required"]],
                },
            }
            for t in tools
        ]

    async def call(
        self, messages: Messages, tools: Optional[list[Tool]] = None
    ) -> LLMResponse:
        anthropic_messages = cast(list[MessageParam], messages.to_list())

        response = await self.client.messages.create(
            max_tokens=1024,
            messages=anthropic_messages,
            model=self.model,
            tools=self.format_tools(tools) if tools else omit,
        )

        # translate anthropic's vendor specific tool call to generic ToolCall object
        tool_calls = [
            ToolCall(
                id=block.id,
                name=block.name,
                arguments=cast(dict[str, Any], block.input),
            )
            for block in response.content
            if isinstance(block, ToolUseBlock)
        ]

        content = "\n".join(
            block.text for block in response.content if isinstance(block, TextBlock)
        )

        return LLMResponse(content=content or None, tool_calls=tool_calls or None)
