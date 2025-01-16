from typing import Any, List, Optional

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

    requirement: Optional[str] = None

    available_tools: ToolCollection = ToolCollection(
        Terminal(),
        StrReplaceEditor(),
        FileLocalizer(requirement=requirement),
        CodeReview(),
        Terminate(),
    )
    special_tool_names: List[str] = Field(
        default_factory=lambda: [Terminate().name, CodeReview().name]
    )

    max_steps: int = 30

    working_dir: str = "."

    async def run(self, requirement: Optional[str] = None) -> str:
        """Execute development task with given or existing requirement."""
        if requirement:
            self.requirement = requirement
            if localizer := self.available_tools.get_tool("file_localizer"):
                localizer.requirement = requirement

        if not self.requirement:
            raise ValueError("No requirement provided")

        return await super().run(requirement=self.requirement)

    async def think(self) -> bool:
        """Process current state and decide next action"""
        # Update working directory
        terminal = self.available_tools.get_tool("execute_command")
        self.working_dir = await terminal.execute(command="pwd")
        self.next_step_prompt = self.next_step_prompt.format(
            current_dir=self.working_dir
        )

        return await super().think()

    def _should_finish_execution(self, name: str, result: Any) -> bool:
        """Override to implement specific code review logic"""
        if name == "code_review":
            return "LGTM" in str(
                result
            )  # FIXME: This is a placeholder for actual code review logic
        return super()._should_finish_execution(name=name, result=result)
