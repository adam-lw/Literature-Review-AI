from typing import Optional

from literature_ai.core.agent.agent.react import Agent
from literature_ai.core.agent.agent.registry import is_registered_agent
from literature_ai.core.agent.prompt.prompt import get_prompt
from literature_ai.core.agent.llm.core import get_llm
from literature_ai.core.agent.memory import MemoryObject
from literature_ai.core.agent.tools import get_all_tools, tool
from literature_ai.core.agent.llm.messages import Messages, MessageLike

@tool(name="spawn_chatbot_agent", description="Spawns a chatbot agent to handle conversational tasks.")
async def spawn_chatbot_agent(context: MessageLike, memory: Optional[dict[str, MemoryObject]] = None):

    return await spawn_agent("chatbot", context=context, memory=memory)

@tool(name="spawn_orchestrator_agent", description="Spawns an orchestrator agent to plan and delegate multi-step work.")
async def spawn_orchestrator_agent(context: MessageLike, memory: Optional[dict[str, MemoryObject]] = None):


    return await spawn_agent(name="orchestrator", context=context, memory=memory)


async def spawn_agent(name: str, context: MessageLike, memory: Optional[dict[str, MemoryObject]] = None):
    if not is_registered_agent(name):
        raise ValueError(
            f"`{name}` is not a registered agent. Register it in "
            "config/core/agent/agents.yaml and add a matching "
            f"config/core/agent/prompts/{name}.md file."
        )

    prompt = get_prompt(name)

    agent_context = Messages([prompt, context])

    agent = Agent(
        instructions=agent_context,
        llm=get_llm("gpt-5-nano"),
        tools=get_all_tools(),
        memory=memory)

    return await agent.run_agent()