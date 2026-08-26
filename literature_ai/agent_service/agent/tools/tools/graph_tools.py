from literature_ai.agent_service.agent.tools.decorators import tool


@tool()
def generate_summary(content: str):
    raise NotImplementedError
