from abc import ABC, abstractmethod
import os
from typing import Optional
from pydantic import BaseModel
import asyncio


class LLM(ABC):
    """
    Parent class for vendor-specific LLM APIs, providing a common interface across vendors.
    """

    def __init__(self):
        pass

    @abstractmethod
    async def call(self, messages: list[dict[str, str]]) -> str:
        """Abstract method for calling an LLM"""
        ...

    def call_sync(self, messages: list[dict[str, str]]) -> str:
        """Helper method for synchronous calling of `call`"""
        return asyncio.run(self.call(messages))


def get_llm(model: str, parser: Optional[BaseModel] = None) -> LLM:
    """
    Get an LLM object for the named model.

    This is a factory method for LLM types.
    """
    # Nest imports to avoid circular dependencies
    from papery.core.llm.openai import OPENAI_MODELS, OpenAiLLM
    from papery.core.llm.anthropic import ANTHROPIC_MODELS, AnthropicLLM
    from papery.core.llm.wrappers import ParsingLLM
    from papery.core.llm.langfuse import LangfuseLLM

    llm: LLM
    # Handle base model assignment
    if model in OPENAI_MODELS:
        llm = OpenAiLLM(model)
    elif model in ANTHROPIC_MODELS:
        llm = AnthropicLLM(model)
    else:
        raise ValueError(f"Model `{model}` not found.")

    # Handle wrappers
    if parser is not None:
        llm = ParsingLLM(llm=llm, schema=parser)

    if os.getenv("LANGFUSE_ENABLED", "0").lower() in (
        "1",
        "true",
        "yes",
    ):
        llm = LangfuseLLM(llm=llm)

    return llm
