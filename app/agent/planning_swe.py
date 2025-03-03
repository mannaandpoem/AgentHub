import time

from pydantic import Field, model_validator

from app.agent.planning import PlanningAgent
from app.tool import Finish, StrReplaceEditor, ToolCollection, Bash
from app.tool.planning import PlanningTool


# SWE-specific prompts
SYSTEM_PROMPT = """
You are an expert software engineer that combines detailed planning with flexible execution to solve complex coding tasks.

AVAILABLE TOOLS:
- bash: Execute shell commands to navigate, inspect files, and run programs
- str_replace_editor: Edit files by replacing strings
- planning: Create and manage structured plans to solve complex tasks
- finish: Signal when you've completed the task

METHODOLOGY:
1. PLAN: Start by creating a comprehensive plan with the planning tool
   - Break down the task into clear, sequential steps
   - Include exploration, implementation, and verification steps

2. EXECUTE WITH ADAPTATION: For each step in your plan:
   - Use bash to explore and understand the codebase
   - Make precise changes with str_replace_editor
   - Continuously validate your understanding and approach
   - Update your plan when you discover new information

3. VERIFY & FINALIZE: Before marking the task complete:
   - Test your solution thoroughly
   - Ensure all planned steps are completed
   - Document any important findings or decisions

Your core strength is combining structured planning with adaptability. Maintain your plan but don't be rigid - update it when necessary as you learn more about the codebase.
"""

NEXT_STEP_PROMPT = """
Based on your current progress, determine your next action:

1. PLAN STATUS: Review your current plan and its progress
2. EXPLORATION: What do you need to understand better about the codebase?
3. IMPLEMENTATION: What specific changes need to be made?
4. VERIFICATION: How can you validate your changes work as expected?

Always explain your reasoning before executing tools, and relate your actions back to your overall plan.
"""


class PlanningSWEAgent(PlanningAgent):
    """
    A software engineering agent that uses planning to solve coding tasks.

    This agent extends PlanningAgent with specific software engineering tools
    and capabilities, including bash commands, code editing, and progress tracking.
    """

    name: str = "PlanningSWEAgent"
    description: str = "An agent that solves software engineering tasks"

    system_prompt: str = SYSTEM_PROMPT
    next_step_prompt: str = NEXT_STEP_PROMPT

    # Add SWE-specific tools to the tool collection
    available_tools: ToolCollection = Field(
        default_factory=lambda: ToolCollection(
            Bash(), StrReplaceEditor(), PlanningTool(), Finish()
        )
    )

    @model_validator(mode="after")
    def initialize_plan_and_verify_tools(self) -> "PlanningSWEAgent":
        """Initialize with software engineering specific settings."""
        self.active_plan_id = f"plan_{int(time.time())}"

        # Ensure all required tools are available
        tool_map = self.available_tools.tool_map
        if "bash" not in tool_map:
            self.available_tools.add_tool(Bash())
        if "str_replace_editor" not in tool_map:
            self.available_tools.add_tool(StrReplaceEditor())

        if "planning" not in tool_map:
            self.available_tools.add_tool(PlanningTool())

        return self

    async def create_initial_plan(self, request: str) -> None:
        """Create an initial plan tailored for software engineering tasks."""
        # Enhance request with software engineering context
        swe_request = (
            f"Software Engineering Task: {request}\n\n"
            "Create a comprehensive plan that includes:\n"
            "1. Exploring and understanding the codebase structure\n"
            "2. Identifying the specific files that need modification\n"
            "3. Implementing the necessary changes\n"
            "4. Testing and verifying the solution"
        )

        # Use the parent method with enhanced request
        await super().create_initial_plan(swe_request)


async def main():
    agent = PlanningSWEAgent()
    result = await agent.run(
        "Help me fix the calculator in /Users/manna/PycharmProjects/AgentHub/workspace/calculator"
    )
    print(result)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
