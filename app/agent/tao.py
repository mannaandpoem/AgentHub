from typing import List

from pydantic import Field

from app.agent.toolcall import ToolCallAgent
from app.prompt.tao import NEXT_STEP_PROMPT, SYSTEM_PROMPT
from app.tool import (
    CodeReview,
    FileLocalizer,
    StrReplaceEditor,
    Terminal,
    Terminate,
    ToolCollection,
)


class TaoAgent(ToolCallAgent):
    """
    An agent that embodies the principles of refined software craftsmanship, adept at incremental development tasks.
    """

    name: str = "tao"
    description: str = "A software engineer agent specializing in elegant and efficient code evolution."

    system_prompt: str = SYSTEM_PROMPT
    next_step_prompt: str = NEXT_STEP_PROMPT

    available_tools: ToolCollection = ToolCollection(
        Terminal(),
        StrReplaceEditor(),
        FileLocalizer(),
        CodeReview(),
        Terminate(),
    )
    special_tool_names: List[str] = Field(default_factory=lambda: [Terminate().name])

    max_steps: int = 30
