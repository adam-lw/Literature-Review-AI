from typing import Optional

from literature_ai.agent_service.agent.memory import MemoryObject, PaperMemoryObject
from literature_ai.agent_service.agent.tools import tool
from literature_ai.agent_service.agent.llm.core import Messages, MessageLike
from literature_ai.agent_service.agent.agent.spawn_agent import spawn_agent

@tool(
        name="spawn_chatbot_agent",
        description="Spawns a chatbot agent to handle conversational tasks.",
        accepts_memory=True,
        memory_type=PaperMemoryObject)
async def spawn_chatbot_agent(context: MessageLike, memory: Optional[dict[str, MemoryObject]] = None):

    response = await spawn_agent("chatbot", context=context, memory_objects=memory)
    return response.as_text()

@tool(
        name="spawn_orchestrator_agent",
        description="Spawns an orchestrator agent to plan and delegate multi-step work.",
        accepts_memory=True,
        memory_type=PaperMemoryObject)
async def spawn_orchestrator_agent(context: MessageLike, memory: Optional[dict[str, MemoryObject]] = None):

    response = await spawn_agent(name="orchestrator", context=context, memory_objects=memory)
    return response.as_text()

