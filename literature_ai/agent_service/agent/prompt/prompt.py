from jinja2 import Environment, FileSystemLoader, StrictUndefined
from typing import Any
from literature_ai.utils import get_project_root

PROMPTS_PATH = get_project_root() / "config" / "core" / "agent" / "prompts"


def get_prompt(name: str, **settings: dict[str, Any]) -> str:
    env = Environment(loader=FileSystemLoader(PROMPTS_PATH), undefined=StrictUndefined)
    template = env.get_template(f"{name}.md")

    return template.render(**settings)
