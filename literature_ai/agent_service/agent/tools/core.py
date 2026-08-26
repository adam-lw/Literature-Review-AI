import importlib
import pkgutil
import os
from dataclasses import dataclass
from typing import Any, Callable, Optional

from literature_ai.agent_service.agent.memory import MemoryObject


TOOL_REGISTRY: dict[str, "Tool"] = {}


@dataclass
class ToolCall:
    """A single tool invocation requested by an LLM."""

    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class Tool:
    """
    A callable registered as an LLM tool.

    `definition` holds everything needed to both advertise the tool to an
    LLM (`description`, `params`) and invoke it once called (`callable`).
    """

    name: str
    definition: dict[str, Any]

    @property
    def description(self) -> str:
        return self.definition["description"]

    @property
    def params(self) -> list[dict[str, Any]]:
        return self.definition["params"]

    @property
    def callable(self) -> Callable:
        return self.definition["callable"]

    @property
    def accepts_memory(self) -> bool:
        return self.definition.get("accepts_memory", False)

    @property
    def memory_type(self) -> Optional[type[MemoryObject]]:
        return self.definition.get("memory_type")

    def invoke(self, **kwargs: Any) -> Any:
        return self.callable(**kwargs)


_NON_TOOL_MODULES = ("core", "__init__", "decorators")


def register_all_tools():
    """
    Dynamically import every module under this tools package (including
    subpackages) to ensure all @tool decorated functions are registered.
    Call this once at startup from a central orchestrator.
    """
    package_dir = os.path.dirname(__file__)
    package_name = __package__ or "literature_ai.agent_service.agent.tools"
    for module_info in pkgutil.walk_packages([package_dir], prefix=f"{package_name}."):
        module_name = module_info.name.rsplit(".", 1)[-1]
        if not module_info.ispkg and module_name not in _NON_TOOL_MODULES:
            importlib.import_module(module_info.name)


def get_tool_by_name(name: str) -> "Tool":
    """
    Retrieve a single registered tool by name.
    Raises ToolNotFoundException if the tool is not found.
    """
    if name not in TOOL_REGISTRY:
        raise ToolNotFoundException(f"Tool '{name}' not found.")
    return TOOL_REGISTRY[name]


def get_tools_by_name(names: list[str]) -> dict[str, "Tool"]:
    """
    Retrieve multiple registered tools by name, keyed by name.
    Raises ToolNotFoundException if any tool is not found.
    """
    return {name: get_tool_by_name(name) for name in names}


def get_all_tools() -> list[Tool]:
    """
    Return a list of all registered tool names.
    """
    return list(TOOL_REGISTRY.values())


class ToolForbiddenException(Exception):
    pass


class ToolNotFoundException(Exception):
    pass
