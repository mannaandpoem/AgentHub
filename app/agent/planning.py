import time
from typing import List, Optional, Literal

from pydantic import Field, model_validator

from app.agent import ToolCallAgent
from app.logger import logger
from app.schema import Message, ToolCall
from app.tool import ToolCollection, Finish
from app.tool.planning import PlanningTool

PLANNING_SYSTEM_PROMPT = """
You are an expert Planning Agent tasked with solving complex problems by creating and managing structured plans.
Your job is:
1. Analyze requests to understand the task scope
2. Create clear, actionable plans with the `planning` tool
3. Execute steps using available tools as needed
4. Track progress and adapt plans dynamically
5. Use `finish` to conclude when the task is complete

Available tools will vary by task but may include:
- `planning`: Create, update, and track plans (commands: create, update, mark_step, etc.)
- `finish`: End the task when complete

Break tasks into logical, sequential steps. Think about dependencies and verification methods.
"""

NEXT_STEP_PROMPT = """
Based on the current state, what's your next step?
Consider:
1. Do you need to create or refine a plan?
2. Are you ready to execute a specific step?
3. Have you completed the task?

Provide reasoning, then select the appropriate tool or action.
"""


class PlanningAgent(ToolCallAgent):
    """
    An agent that creates and manages plans to solve tasks.
    
    This agent uses a planning tool to create and manage structured plans,
    and tracks progress through individual steps until task completion.
    """

    name: str = "PlanningAgent"
    description: str = "An agent that creates and manages plans to solve tasks"

    system_prompt: str = PLANNING_SYSTEM_PROMPT
    next_step_prompt: str = NEXT_STEP_PROMPT

    available_tools: ToolCollection = Field(
        default_factory=lambda: ToolCollection(PlanningTool(), Finish())
    )
    tool_choices: Literal["none", "auto", "required"] = "auto"
    special_tool_names: List[str] = Field(default_factory=lambda: [Finish().name])

    tool_calls: List[ToolCall] = Field(default_factory=list)
    active_plan_id: Optional[str] = Field(default=None)

    max_steps: int = 20

    @model_validator(mode="after")
    def initialize_plan_and_verify_tools(self) -> "PlanningAgent":
        """Initialize the agent with a default plan ID and validate required tools."""
        self.active_plan_id = f"plan_{int(time.time())}"

        if "planning" not in self.available_tools.tool_map:
            self.available_tools.add_tool(PlanningTool())

        return self

    async def think(self) -> bool:
        """Decide the next action based on plan status."""
        prompt = (
            f"CURRENT PLAN STATUS:\n{await self.get_plan()}\n\n{self.next_step_prompt}"
            if self.active_plan_id else self.next_step_prompt
        )
        self.messages.append(Message.user_message(prompt))
        return await super().think()

    async def get_plan(self) -> str:
        """Retrieve the current plan status."""
        if not self.active_plan_id:
            return "No active plan. Please create a plan first."

        result = await self.available_tools.execute(
            name="planning", tool_input={"command": "get", "plan_id": self.active_plan_id}
        )
        return result.output if hasattr(result, "output") else str(result)

    async def run(self, request: Optional[str] = None) -> str:
        """Run the agent with an optional initial request."""
        if request:
            await self.create_initial_plan(request)
        return await super().run()

    async def step(self) -> str:
        """Execute a step and update plan status if needed."""
        result = await super().step()
        if self.active_plan_id and self.tool_calls and self.tool_calls[0].function.name != "planning":
            await self.update_plan_status()
        return result

    async def create_initial_plan(self, request: str) -> None:
        """Create an initial plan based on the request."""
        logger.info(f"Creating initial plan with ID: {self.active_plan_id}")

        messages = [
            Message.user_message(f"Analyze the request and create a plan with ID {self.active_plan_id}: {request}")
        ]
        self.memory.add_messages(messages)
        response = await self.llm.ask_tool(
            messages=messages,
            system_msgs=[Message.system_message(self.system_prompt)],
            tools=self.available_tools.to_params(),
            tool_choice="required"
        )
        assistant_msg = Message.from_tool_calls(content=response.content, tool_calls=response.tool_calls)

        self.memory.add_message(assistant_msg)

        plan_created = False
        for tool_call in response.tool_calls:
            if tool_call.function.name == "planning":
                result = await self.execute_tool(tool_call)
                logger.info(
                    f"Executed tool {tool_call.function.name} with result: {result}"
                )

                # Add tool response to memory
                tool_msg = Message.tool_message(
                    content=result, tool_call_id=tool_call.id, name=tool_call.function.name
                )
                self.memory.add_message(tool_msg)
                plan_created = True
                break

        if not plan_created:
            logger.warning("No plan created from initial request")
            tool_msg = Message.assistant_message("Error: Parameter `plan_id` is required for command: create")
            self.memory.add_message(tool_msg)

    async def update_plan_status(self) -> None:
        """Update the current plan progress based on recent actions."""
        if not self.active_plan_id:
            return

        plan = await self.get_plan()
        # Parse plan to find the first non-completed step
        try:
            plan_lines = plan.splitlines()
            for i, line in enumerate(plan_lines):
                if "[ ]" in line or "[→]" in line:  # not_started or in_progress
                    step_index = i - plan_lines.index("Steps:") - 1  # Adjust for header lines
                    await self.available_tools.execute(
                        name="planning",
                        tool_input={
                            "command": "mark_step",
                            "plan_id": self.active_plan_id,
                            "step_index": step_index,
                            "step_status": "completed"
                        }
                    )
                    logger.info(f"Marked step {step_index} as completed in plan {self.active_plan_id}")
                    break
        except Exception as e:
            logger.warning(f"Failed to update plan status: {e}")


async def main():
    # Configure and run the agent
    agent = PlanningAgent(available_tools=ToolCollection(PlanningTool(), Finish()))
    result = await agent.run("Help me plan a trip to the moon")
    print(result)


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
