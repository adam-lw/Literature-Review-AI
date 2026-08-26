from literature_ai.agent_service.agent.tools.core import Tool

ASK_USER_TOOL = Tool(
    name="ask_user",
    definition={
        "description": (
            "Ask the user a question when you need information only they can "
            "provide before you can continue. Ends your turn immediately - "
            "their reply arrives as a new message the next time you run."
        ),
        "params": [
            {
                "param_name": "question",
                "type": "string",
                "description": "The question to ask the user.",
                "required": True,
            },
            {
                "param_name": "description",
                "type": "string",
                "description": "Additional context or explanation for the question.",
                "required": False,
                "default": "",
            },
            {
                "param_name": "options",
                "type": "object",
                "description": (
                    "Suggested answers, keyed by a short id and mapped to their "
                    "display label. Omit for an open-ended question."
                ),
                "required": False,
                "default": {},
            },
            {
                "param_name": "allows_freetext",
                "type": "boolean",
                "description": "Whether the user may answer with free text instead of picking one of `options`.",
                "required": False,
                "default": True,
            },
        ],
        "callable": lambda **kwargs: kwargs,
    },
)