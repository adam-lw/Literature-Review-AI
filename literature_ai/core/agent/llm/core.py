from abc import ABC, abstractmethod
import os
from typing import Any, Optional, Union
from pydantic import BaseModel
import asyncio

from literature_ai.core.agent.llm.messages import Messages
from literature_ai.core.agent.llm.tool_call import ToolCall
from literature_ai.core.agent.tools import Tool


class LLM(ABC):
    """
    Parent class for vendor-specific LLM APIs, providing a common interface across vendors.
    """

    def __init__(self):
        pass

    @abstractmethod
    async def call(
        self, messages: Messages, tools: Optional[list[Tool]] = None
    ) -> Union[str, list[ToolCall]]:
        """
        Abstract method for calling an LLM.

        Returns the model's text response, or a list of `ToolCall`s if the
        model chose to call one or more of the supplied `tools` instead.
        """
        ...

    @abstractmethod
    def format_tools(self, tools: list[Tool]) -> Any:
        """Translates `Tool` objects into this provider's tool-call schema."""
        ...

    def call_sync(
        self, messages: Messages, tools: Optional[list[Tool]] = None
    ) -> Union[str, list[ToolCall]]:
        """Helper method for synchronous calling of `call`"""
        return asyncio.run(self.call(messages, tools=tools))


def get_llm(model: str, parser: Optional[BaseModel] = None) -> LLM:
    """
    Get an LLM object for the named model.

    This is a factory method for LLM types.
    """
    # Nest imports to avoid circular dependencies
    from literature_ai.core.agent.llm.openai import OPENAI_MODELS, OpenAiLLM
    from literature_ai.core.agent.llm.anthropic import ANTHROPIC_MODELS, AnthropicLLM
    from literature_ai.core.agent.llm.wrappers import ParsingLLM
    from literature_ai.core.agent.llm.langfuse import LangfuseLLM

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
