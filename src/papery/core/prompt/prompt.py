from jinja2 import Environment, FileSystemLoader, StrictUndefined
from typing import Any
from papery.core.utils import get_project_root

prompts_dir = get_project_root() / "data" / "prompts"


def get_prompt(name: str, **settings: dict[str, Any]) -> str:
    env = Environment(loader=FileSystemLoader(prompts_dir), undefined=StrictUndefined)
    template = env.get_template(name)

    rendered_prompt = template.render(**settings)

    return rendered_prompt
