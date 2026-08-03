from literature_ai.core.agent.llm.core import LLM
from pydantic import BaseModel, ValidationError


class ParsingLLM(LLM):
    def __init__(self, llm: LLM, schema: BaseModel):
        self.llm = llm
        self.schema = schema

    async def call(self, messages: list[dict[str, str]]) -> str:
        response = await self.llm.call(messages)

        try:
            self.schema.model_validate_json(response, strict=True)
        except ValidationError as e:
            print(e)

        return response
