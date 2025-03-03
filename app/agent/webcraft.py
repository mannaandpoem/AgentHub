from typing import List

from pydantic import Field

from app.agent.toolcall import ToolCallAgent
from app.prompt.webcraft import NEXT_STEP_PROMPT, SYSTEM_PROMPT
from app.tool import Finish, ToolCollection, Bash
from app.tool.create_web_template import CreateWebTemplate
from app.tool.deploy_web_project import DeployWebProject
from app.tool.oh_editor import OHEditor


class WebCraftAgent(ToolCallAgent):
    """Automated web project architect handling full lifecycle from scaffolding to deployment"""

    name: str = "webcraft"
    description: str = "a web craft that specializes in end-to-end web project setup and deployment."

    system_prompt: str = SYSTEM_PROMPT
    next_step_prompt: str = NEXT_STEP_PROMPT

    available_tools: ToolCollection = ToolCollection(
        CreateWebTemplate(),
        DeployWebProject(),
        Bash(),
        OHEditor(),
        Finish()
    )

    special_tool_names: List[str] = Field(default_factory=lambda: [Finish().name])
    max_steps: int = 30
