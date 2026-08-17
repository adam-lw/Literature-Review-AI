from dataclasses import dataclass
from typing import Any


@dataclass
class ToolCall:
    """A single tool invocation requested by an LLM."""

    id: str
    name: str
    arguments: dict[str, Any]
