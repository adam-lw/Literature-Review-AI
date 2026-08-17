import yaml

from literature_ai.core.utils import get_project_root
from literature_ai.core.agent.prompt.prompt import PROMPTS_PATH

AGENT_REGISTRY_PATH = get_project_root() / "config" / "core" / "agent" / "agents.yaml"


def get_registered_agents() -> list[str]:
    """Return the list of legal agent names declared in the agent registry."""
    with open(AGENT_REGISTRY_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f) or []


def is_registered_agent(name: str) -> bool:
    """
    Check whether `name` is a legal agent.

    An agent is legal if it's listed in the registry AND has a
    correspondingly named prompt file (`<name>.md`) in the prompts
    directory.
    """
    return name in get_registered_agents() and (PROMPTS_PATH / f"{name}.md").is_file()
