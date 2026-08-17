from dataclasses import dataclass
from typing import Iterable, Iterator, Optional, Union


@dataclass
class Message:
    """A single chat message exchanged with an LLM."""

    role: str
    content: str

    def to_dict(self) -> dict[str, str]:
        return {"role": self.role, "content": self.content}


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
            message = Message(**message)
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
                raise ValueError("Cannot assign a Messages with more than one message to a single index")
            message = message[0]
        if isinstance(message, dict):
            message = Message(**message)
        self._messages[index] = message

    def __repr__(self) -> str:
        return f"Messages({self._messages!r})"
