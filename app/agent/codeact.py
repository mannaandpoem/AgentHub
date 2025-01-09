from typing import List

from pydantic import Field

from app.agent.toolcall import ToolCallAgent
from app.prompt.codeact import NEXT_STEP_PROMPT, SYSTEM_PROMPT
from app.tool.bash import Bash
from app.tool.finish import Finish
from app.tool.str_replace_editor import StrReplaceEditor
from app.tool.tool import Tool


class CodeActAgent(ToolCallAgent):
    """An agent that implements the CodeActAgent paradigm for executing code and natural conversations."""

    name: str = "CodeActAgent"
    description: str = "an autonomous AI programmer that interacts directly with the computer to solve tasks."

    system_prompt: str = SYSTEM_PROMPT
    next_step_prompt: str = NEXT_STEP_PROMPT

    tools: List[Tool] = [
        Bash,
        StrReplaceEditor,
        Finish,
    ]  # TODO: Add more tools here for CodeActAgent
    special_tool_commands: List[str] = Field(default_factory=lambda: ["finish"])

    max_steps: int = 30
