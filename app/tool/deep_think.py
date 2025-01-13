from app.tool.base import BaseTool, AgentAwareTool
from app.llm import LLM
from app.schema import Message

DESCRIPTION = "Do deep thinking"

SYSTEM = ("Analyze the situation according to the current state.There are many other tools on the outside that don't "
          "need to think about the impossible, just analyze and think. And analyze whether the task has been "
          "completed.")


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

    async def execute(
        self,
    ):
        llm = LLM(name="think")

        if self.agent:

            messages = self.agent.memory.messages
            thinking = await llm.ask(messages=messages, system_msgs=SYSTEM, stream=False)

            thinking_msg = Message.assistant_message(content=thinking)
            self.agent.memory.messages.append(thinking_msg)
            return thinking
        else:
            raise "Failed to get agent state"

