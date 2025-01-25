from app.agent import ToolCallAgent
from typing import List

from pydantic import Field

from app.prompt.operator import NEXT_STEP_PROMPT, SYSTEM_PROMPT
from app.tool import ToolCollection, Finish, WebRead, Browser, Bash


class Operator(ToolCallAgent):
    name: str = "operator"
    description: str = "an agent that can go to the web to perform tasks for you."

    system_prompt: str = SYSTEM_PROMPT
    next_step_prompt: str = NEXT_STEP_PROMPT

    available_tools: ToolCollection = ToolCollection(
        Bash(),
        Browser(),
        WebRead(),
        Finish()
    )

    special_tool_names: List[str] = Field(default_factory=lambda: [Finish().name])

    max_steps: int = 30
