import importlib
import pkgutil
import os
import inspect
import typing
from dataclasses import dataclass
from typing import Any, Callable, Optional, Union, get_type_hints

from docstring_parser import parse as parse_docstring

from literature_ai.core.agent.memory import MemoryObject


TOOL_REGISTRY: dict[str, "Tool"] = {}

_JSON_TYPES: dict[type, str] = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
    list: "array",
    tuple: "array",
    set: "array",
    dict: "object",
}


def _json_type(python_type: Any) -> str:
    """Maps a Python type annotation to its closest JSON schema type name."""
    origin = typing.get_origin(python_type)

    if origin is Union:
        # Unwrap `Optional[X]` (== `Union[X, None]`) down to X.
        args = [arg for arg in typing.get_args(python_type) if arg is not type(None)]
        return _json_type(args[0]) if args else "string"

    return _JSON_TYPES.get(origin or python_type, "string")


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


def register_all_tools():
    """
    Dynamically import all modules in this tools package to ensure all @tool decorated functions are registered.
    Call this once at startup from a central orchestrator.
    """
    package_dir = os.path.dirname(__file__)
    package_name = __package__ or "literature_ai.core.agent.tools"
    for _, module_name, is_pkg in pkgutil.iter_modules([package_dir]):
        if not is_pkg and module_name not in ("core", "__init__"):
            importlib.import_module(f"{package_name}.{module_name}")


def get_tools_by_name(*names: str) -> Union["Tool", dict[str, "Tool"]]:
    """
    Retrieve one or more registered tools by their name(s).
    If one name is given, returns the Tool. If multiple, returns a dict of Tools keyed by name.
    Raises ToolNotFoundException if any tool is not found.
    """
    found: dict[str, Tool] = {}
    for name in names:
        if name not in TOOL_REGISTRY:
            raise ToolNotFoundException(f"Tool '{name}' not found.")
        found[name] = TOOL_REGISTRY[name]
    if len(found) == 1:
        return found[names[0]]
    return found


def get_all_tools() -> list[Tool]:
    """
    Return a list of all registered tool names.
    """
    return list(TOOL_REGISTRY.values())


def tool(
    name: Optional[str] = None,
    description: Optional[str] = None,
    accepts_memory: bool = False,
    memory_type: Optional[type[MemoryObject]] = None,
):
    """
    Decorator to register a function as a tool for LLMs.

    Builds the tool's LLM-facing definition from the decorator arguments, the
    function signature/type hints, and a numpy-style docstring where provided.

    If `accepts_memory` is True, the decorated function must declare a
    `memory` parameter. It is hidden from the LLM-facing schema and is
    instead injected by the agent at call time, looked up from its `memory`
    store by the `paper_id` argument the LLM supplies. `memory_type`
    optionally restricts which `MemoryObject` subclass the tool accepts.
    """

    def wrapper(func: Callable) -> Callable:
        tool_name = name or func.__name__
        sig = inspect.signature(func)
        type_hints = get_type_hints(func)
        parsed_doc = parse_docstring(func.__doc__ or "")
        doc_params = {p.arg_name: p for p in parsed_doc.params}

        if accepts_memory and "memory" not in sig.parameters:
            raise ValueError(
                f"Tool `{tool_name}` has accepts_memory=True but its function "
                "signature has no `memory` parameter."
            )
        if memory_type is not None and not (
            isinstance(memory_type, type) and issubclass(memory_type, MemoryObject)
        ):
            raise TypeError(f"`memory_type` must be a MemoryObject subclass, got {memory_type!r}.")

        params: list[dict[str, Any]] = []
        for param_name, param in sig.parameters.items():
            if param_name == "self":
                continue
            if accepts_memory and param_name == "memory":
                # Injected by the agent from its memory store, not LLM-supplied.
                continue

            doc_param = doc_params.get(param_name)
            param_info: dict[str, Any] = {
                "param_name": param_name,
                "type": _json_type(type_hints.get(param_name, str)),
                "description": doc_param.description if doc_param else "",
                "required": param.default is inspect.Parameter.empty,
            }
            if param.default is not inspect.Parameter.empty:
                param_info["default"] = param.default

            params.append(param_info)

        tool_description = (
            description or parsed_doc.short_description or ""
        )

        TOOL_REGISTRY[tool_name] = Tool(
            name=tool_name,
            definition={
                "description": tool_description,
                "params": params,
                "callable": func,
                "accepts_memory": accepts_memory,
                "memory_type": memory_type,
            },
        )
        return func

    return wrapper


class ToolForbiddenException(Exception):
    pass


class ToolNotFoundException(Exception):
    pass
