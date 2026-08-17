from literature_ai.core.agent.llm.core import LLM
from literature_ai.core.agent.llm.messages import Messages
from literature_ai.core.agent.llm.tool_call import ToolCall
from literature_ai.core.agent.tools import Tool
from pydantic import BaseModel, ValidationError
from typing import Any, Optional, Union


class ParsingLLM(LLM):
    def __init__(self, llm: LLM, schema: BaseModel):
        self.llm = llm
        self.schema = schema

    def format_tools(self, tools: list[Tool]) -> Any:
        return self.llm.format_tools(tools)

    async def call(
        self, messages: Messages, tools: Optional[list[Tool]] = None
    ) -> Union[str, list[ToolCall]]:
        response = await self.llm.call(messages, tools=tools)

        if isinstance(response, str):
            try:
                self.schema.model_validate_json(response, strict=True)
            except ValidationError as e:
                print(e)

        return response
