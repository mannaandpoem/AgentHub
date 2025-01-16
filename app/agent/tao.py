from typing import List, Optional

from pydantic import Field

from app.agent.toolcall import ToolCallAgent
from app.prompt.tao import NEXT_STEP_PROMPT, SYSTEM_PROMPT
from app.tool import (
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

    requirement: Optional[str] = None

    available_tools: ToolCollection = ToolCollection(
        Terminal(),
        StrReplaceEditor(),
        FileLocalizer(requirement=requirement),
        # CodeReview(),
        Terminate(),
    )
    special_tool_names: List[str] = Field(default_factory=lambda: [Terminate().name])

    max_steps: int = 30

    async def run(self, requirement: Optional[str] = None) -> str:
        """Execute development task with given or existing requirement."""
        if requirement:
            self.requirement = requirement
            if localizer := self.available_tools.get_tool("file_localizer"):
                localizer.requirement = requirement

        if not self.requirement:
            raise ValueError("No requirement provided")

        return await super().run()
