from abc import ABC, abstractmethod
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

    # optional langfuse wrapper
    try:
        from papery.core.llm.langfuse import LangfuseLLM
    except Exception:
        LangfuseLLM = None

    if model in OPENAI_MODELS:
        llm = OpenAiLLM(model)
    elif model in ANTHROPIC_MODELS:
        llm = AnthropicLLM(model)
    else:
        raise ValueError(f"Model `{model}` not found.")

    if parser is not None:
        llm = ParsingLLM(llm=llm, schema=parser)

    # Wrap with langfuse logging wrapper if available and enabled
    try:
        import os

        if LangfuseLLM is not None and os.getenv("LANGFUSE_ENABLED", "0").lower() in (
            "1",
            "true",
            "yes",
        ):
            llm = LangfuseLLM(llm=llm)
    except Exception:
        # don't fail creation if logging wrapper has issues
        pass

    return llm
