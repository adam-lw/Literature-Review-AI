from literature_ai.core.agent.llm import LLM
from literature_ai.core.agent.llm.messages import Messages
from literature_ai.core.agent.llm.tool_call import ToolCall
from literature_ai.core.agent.tools import Tool
from typing import Any, Optional, Union, cast
from anthropic import AsyncAnthropic, omit
from anthropic.types import MessageParam, TextBlock, ToolParam, ToolUseBlock
import os

ANTHROPIC_MODELS = ["claude-3-5-haiku-20241022", "claude-sonnet-4-5-20250929"]


class AnthropicLLM(LLM):
    def __init__(self, model: str, **config: dict[str, Any]):
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
    ) -> Union[str, list[ToolCall]]:
        anthropic_messages = cast(list[MessageParam], messages.to_list())

        response = await self.client.messages.create(
            max_tokens=1024,
            messages=anthropic_messages,
            model=self.model,
            tools=self.format_tools(tools) if tools else omit,
        )

        tool_calls = [
            ToolCall(id=block.id, name=block.name, arguments=cast(dict[str, Any], block.input))
            for block in response.content
            if isinstance(block, ToolUseBlock)
        ]
        if tool_calls:
            return tool_calls

        # Extract text safely
        for block in response.content:
            if isinstance(block, TextBlock):
                return block.text

        raise RuntimeError("No text block returned from Anthropic response")
