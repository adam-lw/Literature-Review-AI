from abc import ABC, abstractmethod
from typing import Optional, Any, Literal


class Agent(ABC):
    """
    Base class for Agents.
    """

    state: Literal["plan", "execute", "reflect", "summarise"]

    def __init__(self, **kwargs):
        self.kwargs = kwargs

    @abstractmethod
    def step(self):
        """
        Perform a single step based on the current state of the context and agent.
        """
        ...

    @abstractmethod
    def _call_tool(self, tool: str): ...
