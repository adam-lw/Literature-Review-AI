from dotenv import load_dotenv
from literature_ai.agent_service.agent.llm.core import LLM, Messages
from literature_ai.agent_service.agent.tools import Tool, ToolCall
import json
import os
from typing import Any, Mapping, Optional, Union, cast

from openai import AsyncOpenAI, omit
from openai.types.responses import FunctionToolParam

load_dotenv()

OPENAI_MODELS = ["gpt-5-nano", "gpt-4o-mini"]


class OpenAiLLM(LLM):
    def __init__(self, model: str, **config: dict[str, Any]):
        self._validate_model(model)
        self.model = model
        self.config = config
        self.client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    def _validate_model(self, model) -> None:
        """Validates that a legal OpenAI model has been passed"""
        if model not in OPENAI_MODELS:
            raise ValueError(
                f"{model} is not a legal OpenAI model. Available models: {OPENAI_MODELS}"
            )

    def format_tools(self, tools: list[Tool]) -> list[FunctionToolParam]:
        return [
            {
                "type": "function",
                "name": t.name,
                "description": t.description,
                "strict": None,
                "parameters": {
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
        messages_text = "\n".join(f"{m.role}: {m.content}" for m in messages)

        config = cast(Mapping[str, Any], self.config)

        response = await self.client.responses.create(
            model=self.model,
            input=messages_text,
            tools=self.format_tools(tools) if tools else omit,
            **config,
        )

        tool_calls = [
            ToolCall(
                id=item.call_id, name=item.name, arguments=json.loads(item.arguments)
            )
            for item in response.output
            if item.type == "function_call"
        ]
        if tool_calls:
            return tool_calls

        return response.output_text
