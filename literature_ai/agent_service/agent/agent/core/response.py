from dataclasses import dataclass, field
from typing import Literal, Optional, Union

from literature_ai.agent_service.agent.llm.core import Message, Messages

AgentStatus = Literal["completed", "awaiting_input", "error"]


@dataclass
class Question:
    """A structured question an agent asks the caller before it can continue."""

    question: str
    description: str = ""
    options: dict[str, str] = field(default_factory=dict)
    allows_freetext: bool = True


@dataclass
class AgentResponse:
    """
    What an agent's `run_agent` loop returns once it stops iterating.

    `state` is the full react context (system/user/assistant/tool messages)
    at the moment the agent stopped, useful for resuming a conversation or
    for debugging. `result` holds the actual payload: a `Message` with the
    agent's final answer when `status` is "completed" or "error", or a
    `Question` when the agent needs input from the caller before it can
    continue (`status` is "awaiting_input").
    """

    status: AgentStatus
    state: Messages
    result: Union[Message, Question]
    reasoning: Optional[str] = None

    def as_text(self) -> str:
        """
        Render this response as a single string.

        Used when an agent's response is fed back into another agent's
        context (e.g. a sub-agent invoked as a tool), which expects a plain
        string tool result rather than a structured `AgentResponse`.
        """
        if isinstance(self.result, Question):
            lines = [f"Needs input: {self.result.question}"]
            if self.result.description:
                lines.append(self.result.description)
            if self.result.options:
                options = ", ".join(f"{k}: {v}" for k, v in self.result.options.items())
                lines.append(f"Options: {options}")
            return "\n".join(lines)

        prefix = "Error: " if self.status == "error" else ""
        return f"{prefix}{self.result.content}"
