from dataclasses import dataclass
from typing import Optional

import yaml

from literature_ai.agent_service.agent.agent.core.react import ReactAgent
from literature_ai.agent_service.agent.agent.core.response import AgentResponse
from literature_ai.agent_service.agent.prompt.prompt import get_prompt, PROMPTS_PATH
from literature_ai.agent_service.agent.llm.core import get_llm, Messages
from literature_ai.agent_service.agent.memory import MemoryObject, get_formatted_memory
from literature_ai.agent_service.agent.tools import (
    Tool,
    get_all_tools,
    get_tools_by_name
)
from literature_ai.agent_service.agent.tools.core import get_agent_context_facts
from literature_ai.agent_service.agent.tools.skills import get_formatted_skills
from literature_ai.utils import get_project_root

AGENT_SETTINGS_PATH = get_project_root() / "config" / "core" / "agent" / "settings"
AGENT_REGISTRY_PATH = get_project_root() / "config" / "core" / "agent" / "agents.yaml"


def get_registered_agents() -> list[str]:
    """Return the list of legal agent names declared in the agent registry."""
    with open(AGENT_REGISTRY_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f) or []


def is_registered_agent(name: str) -> bool:
    """
    Check whether `name` is a legal agent.

    An agent is legal if it's listed in the registry AND has a
    correspondingly named prompt file (`<name>.md`) in the
    `prompts/agent_types` directory.
    """
    return (
        name in get_registered_agents()
        and (PROMPTS_PATH / "agent_types" / f"{name}.md").is_file()
    )


@dataclass
class AgentSettings:
    """An agent's resolved settings: which tools it may call, which LLM backs
    it, and whether it may pause to ask the user a clarifying question."""

    tools: list[Tool]
    llm: str
    allow_questions: bool


def _get_agent_settings(name: str) -> AgentSettings:
    """
    Resolve an agent's settings from `config/core/agent/settings/<name>.yaml`.

    The file may specify:
    - `tools`: a list of tool names. If the key is omitted, or the file
      doesn't exist, every registered tool is made available.
    - `llm`: the model name to run the agent on. Defaults to "gpt-5.6-luna".
    - `allow_questions`: whether the agent may ask the user a clarifying
      question via the `ask_user` tool. Defaults to False.
    """
    settings_path = AGENT_SETTINGS_PATH / f"{name}.yaml"
    settings: dict = {}
    if settings_path.is_file():
        with open(settings_path, encoding="utf-8") as f:
            settings = yaml.safe_load(f) or {}

    tool_names = settings.get("tools")
    tools = (
        get_all_tools()
        if tool_names is None
        else list(get_tools_by_name(tool_names).values())
    )

    return AgentSettings(
        tools=tools,
        llm=settings.get("llm", "gpt-5.6-luna"),
        allow_questions=settings.get("allow_questions", False),
    )


async def spawn_agent(
    name: str,
    instruction: str,
    memory_objects: Optional[dict[str, MemoryObject]] = None,
) -> AgentResponse:
    """
    Creates and runs an agent, running until completion OR until a question is asked

    """

    if not is_registered_agent(name):
        raise ValueError(
            f"`{name}` is not a registered agent. Register it in "
            "config/core/agent/agents.yaml and add a matching "
            f"config/core/agent/prompts/agent_types/{name}.md file."
        )

    # build agent system prompt:
    # - react boilerplate prompt
    # - specific agent prompt / definition / instructions
    # - list available skills
    # - a summary of the agent's available memory objects (papers, generations, etc)
    react_prompt = get_prompt("agent_core/react")
    agent_prompt = get_prompt(f"agent_types/{name}")
    skills = get_formatted_skills()
    memory_summary = get_formatted_memory(memory_objects)
    additional_information = get_agent_context_facts()

    system_prompt = "\n".join([react_prompt, agent_prompt, skills, memory_summary, additional_information])

    # retrieve additional settings
    settings = _get_agent_settings(name)
    llm = get_llm(settings.llm)

    agent = ReactAgent(
        system_prompt=system_prompt,
        llm=llm,
        tools=settings.tools,
        memory=memory_objects,
        allow_questions=settings.allow_questions,
    )

    return await agent.run_agent(content=instruction)


async def resume_agent(
    name: str,
    history: Messages,
    instruction: str,
    memory_objects: Optional[dict[str, MemoryObject]] = None,
) -> AgentResponse:
    """
    Resumes an agent from a previously returned `AgentResponse.state`.

    `history[0]` — the fully composed system prompt built by the original
    `spawn_agent` call — seeds the fresh `ReactAgent`. The rest of `history`
    plus the new `instruction` (appended as a user turn) are replayed into
    its context via `run_agent`'s `content` parameter before it continues
    iterating.
    """
    if not is_registered_agent(name):
        raise ValueError(
            f"`{name}` is not a registered agent. Register it in "
            "config/core/agent/agents.yaml and add a matching "
            f"config/core/agent/prompts/agent_types/{name}.md file."
        )

    settings = _get_agent_settings(name)
    llm = get_llm(settings.llm)

    agent = ReactAgent(
        system_prompt=history[0].content,
        llm=llm,
        tools=settings.tools,
        memory=memory_objects,
        allow_questions=settings.allow_questions,
    )

    remainder = Messages(list(history)[1:])
    remainder.add_user(instruction)

    return await agent.run_agent(content=remainder)
