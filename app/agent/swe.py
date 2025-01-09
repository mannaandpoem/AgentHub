from app.agent.codeact import CodeActAgent
from app.prompts.swe import NEXT_STEP_TEMPLATE, SYSTEM_PROMPT


class SWEAgent(CodeActAgent):
    """An agent that implements the SWEAgent paradigm for executing code and natural conversations."""

    name: str = "SWEAgent"
    description: str = "an autonomous AI programmer that interacts directly with the computer to solve tasks."

    system_prompt: str = SYSTEM_PROMPT
    next_step_prompt: str = NEXT_STEP_TEMPLATE
