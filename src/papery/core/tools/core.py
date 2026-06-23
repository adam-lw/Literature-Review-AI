import importlib
import pkgutil
import os

TOOL_REGISTRY = []

def register_all_tools():
    """
    Dynamically import all modules in this tools package to ensure all @tool decorated functions are registered.
    Call this once at startup from a central orchestrator.
    """
    package_dir = os.path.dirname(__file__)
    package_name = __package__ or 'papery.core.tools'
    for _, module_name, is_pkg in pkgutil.iter_modules([package_dir]):
        if not is_pkg and module_name not in ("core", "decorators", "__init__"):
            importlib.import_module(f"{package_name}.{module_name}")


def get_tools(*names: str):
    """
    Retrieve one or more registered tool callables by their name(s).
    If one name is given, returns the callable. If multiple, returns a list of callables in the same order.
    Raises ToolNotFoundException if any tool is not found.
    """
    found = {}
    for name in names:
        for tool_info in TOOL_REGISTRY:
            if tool_info["name"] == name:
                found[name] = tool_info
                break
        else:
            raise ToolNotFoundException(f"Tool '{name}' not found.")
    if len(found) == 1:
        return found[names[0]]
    return found

def list_tools():
    """
    Return a list of all registered tool names.
    """
    return [tool_info["name"] for tool_info in TOOL_REGISTRY]

class ToolForbiddenException(Exception):
    pass


class ToolNotFoundException(Exception):
    pass
