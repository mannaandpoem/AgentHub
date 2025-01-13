from typing import List

from pydantic import Field

from app.agent.toolcall import ToolCallAgent
from app.prompt.codeact import NEXT_STEP_PROMPT, SYSTEM_PROMPT
from app.tool import Finish, Terminal, ToolCollection, PythonExecute, DeepThink


class CodeActAgent(ToolCallAgent):
    """An agent that implements the CodeActAgent paradigm for executing code and natural conversations."""

    name: str = "CodeActAgent"
    description: str = "an autonomous AI programmer that interacts directly with the computer to solve tasks."

    system_prompt: str = SYSTEM_PROMPT
    next_step_prompt: str = NEXT_STEP_PROMPT

    fixed_tools: ToolCollection = ToolCollection(
        DeepThink()
    )

    agent_tools: ToolCollection = ToolCollection(
        # Terminal(), StrReplaceEditor(), Finish()
        PythonExecute(), Finish()
    )  # TODO: Add more tools here for CodeActAgent
    special_tools: List[str] = Field(
        default_factory=lambda: [Finish.get_name().lower()]
    )

    max_steps: int = 30
