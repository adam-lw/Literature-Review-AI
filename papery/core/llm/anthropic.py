from papery.core.llm import LLM
from typing import Any
from anthropic import Anthropic
import os

ANTHROPIC_MODELS = ["claude-3-5-haiku-20241022", "claude-sonnet-4-5-20250929"]


class AnthropicLLM(LLM):
    def __init__(self, model: str, **config: dict[str, Any]):
        self._validate_model(model=model)
        self.model = model
        self.client = Anthropic(
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

    async def call(self, messages: list[dict[str, str]]) -> str:
        message = self.client.messages.create(
            max_tokens=1024,
            messages=messages,
            model=self.model,
        )
        return message.content[0].text
