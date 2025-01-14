from app.llm import LLM
from app.schema import Message
from app.tool.base import AgentAwareTool, BaseTool


DESCRIPTION = "Do deep thinking"

SYSTEM = (
    "Analyze the situation according to the current state.There are many other tools on the outside that don't "
    "need to think about the impossible, just analyze and think. And analyze whether the task has been "
    "completed."
)


class DeepThink(BaseTool, AgentAwareTool):
    """A tool for executing Python code with timeout and safety restrictions."""

    name: str = "deep_think"
    description: str = DESCRIPTION
    parameters: dict = {
        "type": "object",
        "properties": {
            "context": {
                "type": "string",
                "description": "Current context and background",
            },
        },
        "required": ["context"],
    }

    llm: LLM | None = None

    def __init__(self):
        super().__init__()
        self.llm = LLM()

    async def execute(self, context: str = ""):
        if not self.agent:
            raise ValueError("Failed to get agent state")

        if not self.llm:
            raise ValueError("LLM not initialized")

        messages = self.agent.memory.messages
        thinking = await self.llm.ask(
            messages=messages, system_msgs=SYSTEM, stream=False
        )

        thinking_msg = Message.assistant_message(content=thinking)
        self.agent.memory.messages.append(thinking_msg)
        return thinking
