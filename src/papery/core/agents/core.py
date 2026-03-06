from abc import ABC, abstractmethod


class Agent(ABC):
    """
    Base class for Agents.
    """

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
