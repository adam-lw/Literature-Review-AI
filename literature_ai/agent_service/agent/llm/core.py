from abc import ABC, abstractmethod
import asyncio
from dataclasses import dataclass
from typing import Any, Iterable, Iterator, Optional, Union
from pydantic import BaseModel

from literature_ai.agent_service.agent.tools import Tool, ToolCall


@dataclass
class Message:
    """A single chat message exchanged with an LLM."""

    role: str
    content: str

    def to_dict(self) -> dict[str, str]:
        return {"role": self.role, "content": self.content}


@dataclass
class LLMResponse:
    """
    The result of a single `LLM.call`.

    `content` holds the model's text response (reasoning and/or a final
    answer), and `tool_calls` holds any tools the model chose to invoke.
    Both may be populated at once - a model can emit reasoning text
    alongside a tool call in the same turn.
    """

    content: Optional[str] = None
    tool_calls: Optional[list[ToolCall]] = None


MessageLike = Union[Message, dict[str, str], str, "Messages"]


class Messages:
    """
    Ordered collection of chat messages.

    Replaces raw `list[dict[str, str]]` objects as the interface between
    prompt-building code and the generic `LLM` interface. Vendor-specific
    `LLM` implementations convert a `Messages` instance to whatever shape
    their SDK expects via `to_list()` or by iterating over it directly.

    `Messages` is itself a `MessageLike`, so a new `Messages` can be built
    from other `Messages` instances (e.g. `Messages([msgs1, msgs2])` or
    `msgs.append(other_msgs)`), which flattens them in place.
    """

    def __init__(self, messages: Optional[Iterable[MessageLike]] = None):
        self._messages: list[Message] = []
        for message in messages or []:
            self.append(message)

    def append(self, message: MessageLike) -> "Messages":
        if isinstance(message, Messages):
            self._messages.extend(message._messages)
            return self
        if isinstance(message, str):
            message = Message(role="system", content=message)
        elif isinstance(message, dict):
            if "role" in message and "content" in message:
                message = Message(**message)
            else:
                # Shorthand form, e.g. `{"system": "..."}` / `{"user": "..."}`:
                # the single key is the role, its value the content.
                ((role, content),) = message.items()
                message = Message(role=role, content=content)
        self._messages.append(message)
        return self

    def add(self, content: str, role: str) -> "Messages":
        return self.append(Message(role=role, content=content))

    def add_system(self, content: str) -> "Messages":
        return self.append(Message(role="system", content=content))

    def add_user(self, content: str) -> "Messages":
        return self.append(Message(role="user", content=content))

    def add_assistant(self, content: str) -> "Messages":
        return self.append(Message(role="assistant", content=content))

    def to_list(self) -> list[dict[str, str]]:
        """Renders these messages as the raw `list[dict[str, str]]` form vendor SDKs expect."""
        return [message.to_dict() for message in self._messages]

    def __iter__(self) -> Iterator[Message]:
        return iter(self._messages)

    def __len__(self) -> int:
        return len(self._messages)

    def __getitem__(self, index: int) -> Message:
        return self._messages[index]

    def __setitem__(self, index: int, message: MessageLike) -> None:
        if isinstance(message, Messages):
            if len(message) != 1:
                raise ValueError(
                    "Cannot assign a Messages with more than one message to a single index"
                )
            message = message[0]
        if isinstance(message, dict):
            message = Message(**message)
        self._messages[index] = message

    def __repr__(self) -> str:
        return f"Messages({self._messages!r})"


class LLM(ABC):
    """
    Parent class for vendor-specific LLM APIs, providing a common interface across vendors.
    """

    def __init__(self):
        pass

    @abstractmethod
    async def call(
        self, messages: Messages, tools: Optional[list[Tool]] = None
    ) -> LLMResponse:
        """
        Abstract method for calling an LLM.

        Returns an `LLMResponse` carrying the model's text response, any
        `ToolCall`s the model chose to make against the supplied `tools`, or
        both at once.
        """
        ...

    @abstractmethod
    def format_tools(self, tools: list[Tool]) -> Any:
        """Translates `Tool` objects into this provider's tool-call schema."""
        ...

    def call_sync(
        self, messages: Messages, tools: Optional[list[Tool]] = None
    ) -> LLMResponse:
        """Helper method for synchronous calling of `call`"""
        return asyncio.run(self.call(messages, tools=tools))


def get_llm(model: str, parser: Optional[BaseModel] = None) -> LLM:
    """
    Get an LLM object for the named model.

    This is a factory method for LLM types.
    """
    # Nest imports to avoid circular dependencies
    from literature_ai.agent_service.agent.llm.openai import OPENAI_MODELS, OpenAiLLM
    from literature_ai.agent_service.agent.llm.anthropic import (
        ANTHROPIC_MODELS,
        AnthropicLLM,
    )
    from literature_ai.agent_service.agent.llm.dummy import DummyLLM
    from literature_ai.agent_service.agent.llm.wrappers import ParsingLLM
    from literature_ai.agent_service.agent.llm.langfuse import LangfuseLLM

    llm: LLM
    # Handle base model assignment
    if model == "dummy":
        llm = DummyLLM(model)
    elif model in OPENAI_MODELS:
        llm = OpenAiLLM(model)
    elif model in ANTHROPIC_MODELS:
        llm = AnthropicLLM(model)
    else:
        raise ValueError(f"Model `{model}` not found.")

    # Handle wrappers
    if parser is not None:
        llm = ParsingLLM(llm=llm, schema=parser)

    # wrap the LLM object with a logger
    llm = LangfuseLLM(llm=llm)

    return llm
