from jinja2 import Environment, FileSystemLoader, StrictUndefined
from typing import Any
from literature_ai.core.utils import get_project_root, load_dict

_SETTINGS_PATH = get_project_root() / "config/core/settings.yaml"


def get_prompt(name: str, **settings: dict[str, Any]) -> str:
    prompts_dir = get_project_root() / load_dict(_SETTINGS_PATH)["prompts_path"]
    env = Environment(loader=FileSystemLoader(prompts_dir), undefined=StrictUndefined)
    template = env.get_template(name)

    rendered_prompt = template.render(**settings)

    return rendered_prompt
