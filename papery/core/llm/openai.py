from dotenv import load_dotenv
from papery.core.llm.core import LLM
import os
from typing import Any

from openai import AsyncOpenAI

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

    async def call(self, messages: list[dict[str, str]]) -> str:
        messages_text = "\n".join(f"{m['role']}: {m['content']}" for m in messages)
        response = self.client.responses.create(
            model=self.model, input=messages_text, **self.config
        )
        return response.output_text
