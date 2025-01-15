from typing import List

from pydantic import Field

from app.agent.toolcall import ToolCallAgent
from app.prompt.codeact import NEXT_STEP_PROMPT, SYSTEM_PROMPT
from app.tool import Finish, StrReplaceEditor, Terminal, ToolCollection


class CodeActAgent(ToolCallAgent):
    """An agent that implements the CodeActAgent paradigm for executing code and natural conversations."""

    name: str = "codeact"
    description: str = "an autonomous AI programmer that interacts directly with the computer to solve tasks."

    system_prompt: str = SYSTEM_PROMPT
    next_step_prompt: str = NEXT_STEP_PROMPT

    available_tools: ToolCollection = ToolCollection(
        Terminal(), StrReplaceEditor(), Finish()
    )
    special_tool_names: List[str] = Field(default_factory=lambda: [Finish().name])

    max_steps: int = 30
