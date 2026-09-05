import yaml

from literature_ai.utils import get_project_root

SKILLS_PATH = get_project_root() / "config" / "core" / "agent" / "skills"

SKILLS: list[dict[str, str]] = []


def _parse_frontmatter(text: str) -> dict[str, str]:
    """Extracts the leading `---`-delimited YAML frontmatter block from a SKILL.md file."""
    if not text.startswith("---"):
        return {}

    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}

    return yaml.safe_load(parts[1]) or {}


def register_skills():
    """
    Discover all skills from file and store them in SKILLS.

    Format:
    [
        {
            name: str,
            description: str,
            full_content: str
        }
    ]
    """
    SKILLS.clear()

    if not SKILLS_PATH.is_dir():
        return

    for skill_file in sorted(SKILLS_PATH.glob("*/SKILL.md")):
        full_content = skill_file.read_text(encoding="utf-8")
        frontmatter = _parse_frontmatter(full_content)

        SKILLS.append(
            {
                "name": frontmatter.get("name", skill_file.parent.name),
                "description": frontmatter.get("description", ""),
                "full_content": full_content,
            }
        )


def get_skills() -> list[dict[str, str]]:
    """
    Return a list of {name: str, description: str} as loaded from the project's SKILL.md files
    """
    if len(SKILLS) == 0:
        register_skills()
    return [{"name": s["name"], "description": s["description"]} for s in SKILLS]


def get_formatted_skills() -> str:
    """
    Returns a string defining all skills for use by an LLM.
    """
    skills = get_skills()

    if not skills:
        return "No skills are currently available."

    skill_lines = "\n".join(f"- {s['name']}: {s['description']}" for s in skills)
    return (
        "\n## Skills:\n\nThe following skills are available. Call `load_skill` with the exact "
        "name of a skill to load its full instructions before using it.\n"
        f"{skill_lines}"
    )
