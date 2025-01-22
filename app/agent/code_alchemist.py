from typing import List

from pydantic import Field

from app.agent import ToolCallAgent
from app.prompt.code_alchemist import SYSTEM_PROMPT, NEXT_STEP_PROMPT
from app.tool import ToolCollection, AttemptCompletion, Bash, ListFiles
from app.tool.refine_code import RefineCode
from app.tool.view import View
from app.tool.write_code import WriteCode


class CodeAlchemistAgent(ToolCallAgent):
    """An agent that transforms requirements into elegant code solutions."""
    name: str = "code_alchemist"
    description: str = "a sophisticated AI programmer that transforms requirements into elegant code solutions."
    system_prompt: str = SYSTEM_PROMPT
    next_step_prompt: str = NEXT_STEP_PROMPT

    # Tool configuration
    available_tools: ToolCollection = ToolCollection(
        Bash(),
        WriteCode(),
        RefineCode(),
        View(),
        ListFiles(),
        AttemptCompletion()
    )
    special_tool_names: List[str] = Field(
        default_factory=lambda: [AttemptCompletion().name]
    )

    max_steps: int = 30
