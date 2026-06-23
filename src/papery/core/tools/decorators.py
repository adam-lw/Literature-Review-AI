import inspect
from typing import Callable, Optional, get_type_hints, Any, Dict
from .core import TOOL_REGISTRY


def tool(
    name: Optional[str] = None,
    description: Optional[str] = None,
):
    """
    Decorator to register a function as a tool for LLMs.
    Logs tool name, description, input/output schema, and docstring info.
    """

    def wrapper(func: Callable):
        sig = inspect.signature(func)
        type_hints = get_type_hints(func)

        # Build input schema from signature and type hints
        input_schema: Dict[str, Any] = {}
        for param_name, param in sig.parameters.items():
            param_type = type_hints.get(param_name, Any)
            input_schema[param_name] = str(param_type)

        # Output schema (if annotated)
        output_schema = str(type_hints.get("return", Any))

        # Use docstring for input/output descriptions if available
        doc = func.__doc__ or ""

        tool_info = {
            "name": name if name else func.__name__,
            "description": description
            if description
            else doc.strip().split("\n")[0]
            if doc
            else "",
            "func": func,
            "input_schema": input_schema,
            "output_schema": output_schema,
            "docstring": doc,
        }

        TOOL_REGISTRY.append(tool_info)
        return func

    return wrapper
