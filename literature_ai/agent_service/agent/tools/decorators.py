import inspect
from typing import Any, Callable, Optional, get_type_hints

from docstring_parser import parse as parse_docstring

from literature_ai.agent_service.agent.memory import MemoryObject
from literature_ai.agent_service.agent.tools.core import TOOL_REGISTRY, Tool


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

        # Process parameters of decorated functions
        # We need this to automatically generate LLM-passable tool definitions
        # We skip "self" and "memory" parameters
        params: list[dict[str, Any]] = []
        for param_name, param in sig.parameters.items():
            if param_name == "self":
                continue
            if accepts_memory and param_name == "memory":
                # Injected by the agent from its memory store, not LLM-supplied.
                continue

            doc_param = doc_params.get(param_name)
            param_type = type_hints.get(param_name, str)
            param_info: dict[str, Any] = {
                "param_name": param_name,
                "type": getattr(param_type, "__name__", str(param_type)),
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
