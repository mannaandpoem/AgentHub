from app.agent import ToolCallAgent
from typing import List

from pydantic import Field, model_validator

from app.prompt.snap_coder import NEXT_STEP_PROMPT, SYSTEM_PROMPT
from app.tool import Finish, ToolCollection, Bash
from app.tool.oh_editor import OHEditor
from app.tool.screenshot_to_code import ScreenshotToCodeTool


class SnapCoder(ToolCallAgent):
    """An agent that converts screenshots into React/Tailwind code"""

    name: str = "snap_coder"
    description: str = "An AI agent that converts screenshots into high-quality React/Tailwind code"

    system_prompt: str = SYSTEM_PROMPT
    next_step_prompt: str = NEXT_STEP_PROMPT

    available_tools: ToolCollection = ToolCollection(
        ScreenshotToCodeTool(), Finish()
    )

    special_tool_names: List[str] = Field(default_factory=lambda: [Finish().name])

    max_steps: int = 30

    screenshot_key: str = Field(default=None)

    @model_validator(mode='after')
    def update_screenshot_tool_key(self) -> 'SnapCoder':
        if self.screenshot_key is not None:
            # Find ScreenshotToCodeTool instance and update it
            if screenshot_to_code_tool := self.available_tools.get_tool("screenshot_to_code"):
                screenshot_to_code_tool.screenshot_key = self.screenshot_key
        return self
