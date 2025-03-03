from typing import List

from pydantic import Field

from app.agent import ToolCallAgent
from app.prompt.operator import NEXT_STEP_PROMPT, SYSTEM_PROMPT
from app.schema import Message, AgentState
from app.tool import ToolCollection, Finish
from app.tool.browser_use_tool import BrowserUseTool


class Operator(ToolCallAgent):
    name: str = "operator"
    description: str = "an agent that can go to the web to perform tasks for you."

    system_prompt: str = SYSTEM_PROMPT
    next_step_prompt: str = NEXT_STEP_PROMPT

    available_tools: ToolCollection = ToolCollection(
        BrowserUseTool(),
        Finish()
    )

    special_tool_names: List[str] = Field(default_factory=lambda: [Finish().name])

    max_steps: int = 30


async def main():
    operator = Operator()
    operator.messages.append(Message.user_message("Please browse the web and find today's weather in New York"))

    while operator.state != AgentState.FINISHED:
        thinking_result = await operator.think()
        if thinking_result:
            result = await operator.act()
            print(f"Agent response: {result}")


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
