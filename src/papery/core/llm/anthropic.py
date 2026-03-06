from papery.core.llm import LLM
from typing import Any, cast
from anthropic import AsyncAnthropic
from anthropic.types import MessageParam, TextBlock
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

    async def call(self, messages: list[dict[str, str]]) -> str:
        anthropic_messages = cast(list[MessageParam], messages)

        response = await self.client.messages.create(
            max_tokens=1024,
            messages=anthropic_messages,
            model=self.model,
        )

        # Extract text safely
        for block in response.content:
            if isinstance(block, TextBlock):
                return block.text

        raise RuntimeError("No text block returned from Anthropic response")
