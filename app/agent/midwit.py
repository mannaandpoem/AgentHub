from typing import List

from app.agent.codeact import CodeActAgent
from app.prompts.midwit import NEXT_STEP_PROMPT, SYSTEM_PROMPT
from app.tool.attempt_completion import AttemptCompletion
from app.tool.list_files import ListFiles
from app.tool.search_file import SearchFile
from app.tool.str_replace_editor import StrReplaceEditor
from app.tool.terminal import Terminal
from app.tool.tool import Tool


class MidwitAgent(CodeActAgent):
    """An agent that implements the MidwitAgent paradigm for executing code and natural conversations."""

    name: str = "MidwitAgent"
    description: str = "a brilliant and meticulous engineer assigned to help the user with any query they have."

    system_prompt: str = SYSTEM_PROMPT
    next_step_prompt: str = NEXT_STEP_PROMPT

    tools: List[Tool] = [
        Terminal,
        StrReplaceEditor,
        SearchFile,
        ListFiles,
        AttemptCompletion,
    ]

    max_steps: int = 30
