import json
import yaml
from typing import Any
from pathlib import Path


def load_dict(path: Path | str) -> dict[str, Any]:
    """Loads a json or yaml file from the provided path. Infers type automatically."""

    if str(path).endswith(".json"):
        with open(path) as f:
            loaded_dict = json.load(f)
    elif str(path).endswith(".yaml"):
        with open(path) as f:
            loaded_dict = yaml.safe_load(f)
    else:
        raise ValueError(f"Unrecognised path suffix {path.split('.')[-1]}")

    return loaded_dict


def save_dict(to_save: dict[str, Any], path: Path | str) -> dict[str, Any]:
    """Saves a Python dictionary to the provided path. Infers type automatically."""

    if not isinstance(to_save, dict):
        raise ValueError(
            f"Failed to save dictionary: {to_save} is not a valid dictionary."
        )

    if str(path).endswith(".json"):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(to_save, f, indent=4)
    elif str(path).endswith(".yaml"):
        with open(path, "w", encoding="utf-8") as f:
            yaml.safe_dump(to_save, f, sort_keys=False)
    else:
        raise ValueError(f"Unrecognised path suffix {path.split('.')[-1]}")


def get_project_root() -> Path:
    """Find the nearest pyproject.toml by walking up the directory tree."""
    current = Path(__file__).resolve().parent

    while current != current.parent:  # until we reach filesystem root
        if (current / "pyproject.toml").is_file():
            return current
        current = current.parent

    raise FileNotFoundError("Could not find pyproject.toml in any parent directory")


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Recursively merges two dictionaries, with values from `override` taking precedence."""
    merged = base.copy()
    for key, value in override.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_prompt(prompt_uri: str):
    """Loads a prompt from the prompts directory based on the provided URI."""
    SETTINGS = load_dict(get_project_root() / "config/core/settings.yaml")
    prompt_path = get_project_root() / SETTINGS["prompts_path"] / prompt_uri

    if not prompt_path.is_file():
        raise FileNotFoundError(f"Prompt file not found at {prompt_path}")

    with open(prompt_path, "r", encoding="utf-8") as f:
        return f.read()
