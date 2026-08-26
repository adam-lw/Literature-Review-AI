from literature_ai.agent_service.agent.tools.decorators import tool
from literature_ai.agent_service.agent.tools.skills import SKILLS, register_skills


@tool(name="load_skill", description="Loads a skill by name. Should match a skill name exactly.")
def load_skill(skill_name: str) -> str:
    """
    Load a SKILL.md file by name and return its contents as a string.
    """
    if len(SKILLS) == 0:
        register_skills()

    skills_dict = {skill["name"]: skill["full_content"] for skill in SKILLS}

    loaded_skill = skills_dict.get(skill_name, None)

    if loaded_skill is None:
        raise ValueError(f"Skill `{skill_name}` was not found.")

    return loaded_skill
