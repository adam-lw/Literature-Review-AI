from literature_ai.agent_service.agent.llm.core import LLM, LLMResponse, Messages
from literature_ai.agent_service.agent.tools import Tool
from pydantic import BaseModel, ValidationError
from typing import Any, Optional


class ParsingLLM(LLM):
    def __init__(self, llm: LLM, schema: BaseModel):
        self.llm = llm
        self.schema = schema

    def format_tools(self, tools: list[Tool]) -> Any:
        return self.llm.format_tools(tools)

    async def call(
        self, messages: Messages, tools: Optional[list[Tool]] = None
    ) -> LLMResponse:
        response = await self.llm.call(messages, tools=tools)

        if response.content is not None:
            try:
                self.schema.model_validate_json(response.content, strict=True)
            except ValidationError as e:
                print(e)

        return response
