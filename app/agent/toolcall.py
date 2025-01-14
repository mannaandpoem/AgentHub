import asyncio
import json
from typing import List, Literal, Optional

from pydantic import Field

from app.agent.base import BaseAgent
from app.exceptions import ToolError
from app.logger import logger
from app.prompt.toolcall import NEXT_STEP_PROMPT, SYSTEM_PROMPT
from app.schema import AgentState, Message, ToolCall
from app.tool import Bash, Finish, ToolCollection
from app.tool.base import AgentAwareTool


class ToolCallAgent(BaseAgent):
    """Base agent class for handling tool/function calls with enhanced abstraction"""

    name: str = "ToolCallAgent"
    description: str = "an agent that can execute tool calls."

    system_prompt: str = SYSTEM_PROMPT
    next_step_prompt: str = NEXT_STEP_PROMPT

    fixed_actions: ToolCollection = ToolCollection()
    tool_collection: ToolCollection = ToolCollection(Bash(), Finish())
    tool_choices: Literal["none", "auto", "required"] = "auto"
    special_tools: List[str] = Field(
        default_factory=lambda: [Finish.get_name().lower()]
    )

    commands: List[ToolCall] = Field(default_factory=list)

    max_steps: int = 30

    duplicate_threshold: int = (
        2  # Number of allowed identical responses before considering stuck
    )

    def is_stuck(self) -> bool:
        """Check if the agent is stuck in a loop by detecting duplicate content"""
        if len(self.memory.messages) < 2:
            return False

        last_message = self.memory.messages[-1]
        if not last_message.content:
            return False

        # Count identical content occurrences
        duplicate_count = sum(
            1
            for msg in reversed(self.memory.messages[:-1])
            if msg.role == "assistant" and msg.content == last_message.content
        )

        return duplicate_count >= self.duplicate_threshold

    def handle_stuck_state(self):
        """Handle stuck state by adding a prompt to change strategy"""
        stuck_prompt = "Observed duplicate responses. Consider changing strategy or terminating the interaction."
        self.next_step_prompt = f"{stuck_prompt}\n{self.next_step_prompt}"
        logger.warning(f"Agent detected stuck state. Added prompt: {stuck_prompt}")

    async def run(self, request: Optional[str] = None) -> str:
        """Main execution loop"""
        if request:
            self.update_memory("user", request)

        results = []
        async with self.state_context(AgentState.RUNNING):
            while self.current_step < self.max_steps:
                try:
                    self.current_step += 1

                    await self.fixed_act()

                    # Think phase
                    should_act = await self.think()
                    if not should_act:
                        if self.tool_choices == "required":
                            raise ValueError("Tool calls required but none provided")
                        results.append("Thinking complete - no action needed")
                        break

                    # Check for stuck state
                    if self.is_stuck():
                        self.handle_stuck_state()

                    # Act phase
                    result = await self.act()
                    results.append(f"Step {self.current_step}: {result}")

                    if self.state == AgentState.FINISHED:
                        break

                except Exception as e:
                    error_msg = f"Error in step {self.current_step}: {str(e)}"
                    logger.error(error_msg)
                    results.append(error_msg)
                    break

                await asyncio.sleep(0)

            return "\n".join(results)

    async def fixed_act(self) -> str:
        """Execute fixed tool before agent decision"""
        # Set agent for agent-aware tools
        for tool in self.fixed_actions:
            if isinstance(tool, AgentAwareTool):
                tool.agent = self

        # Execute all tools sequentially
        results = await self.fixed_actions.execute_all()

        # Convert to string format and Log results
        str_results = "\n\n".join([str(r) for r in results])
        logger.info(f"Fixed action result: {str_results}")

        return str_results

    async def think(self) -> bool:
        """Process current state and decide next actions using tools"""
        messages = self.memory.messages
        if self.next_step_prompt:
            user_msg = Message.user_message(self.next_step_prompt)
            messages = messages + [user_msg]

        response = await self.llm.ask_tool(
            messages=messages,
            system_msgs=[self.system_prompt] if self.system_prompt else None,
            tools=self.tool_collection.to_params(),
            tool_choice=self.tool_choices,
        )
        self.commands = response.tool_calls

        logger.info(f"Tool content: {response.content}")
        logger.info(f"Tool calls: {response.tool_calls}")

        # Handle different tool_choices modes
        if self.tool_choices == "none":
            if response.tool_calls:
                logger.warning("Tool calls provided when tool_choice is 'none'")
            if response.content:
                self.memory.add_message(Message.assistant_message(response.content))
                return True
            return False

        # Create and add assistant message
        assistant_msg = (
            Message.from_tool_calls(content=response.content, tool_calls=self.commands)
            if self.commands
            else Message.assistant_message(response.content)
        )
        self.memory.add_message(assistant_msg)

        if self.tool_choices == "required" and not self.commands:
            return True  # Will be handled in run()

        # For 'auto' mode, continue with content if no commands but content exists
        if self.tool_choices == "auto" and not self.commands:
            return bool(response.content)

        return bool(self.commands)

    async def act(self) -> str:
        """Execute tool calls and handle their results"""
        if not self.commands:
            if self.tool_choices == "required":
                raise ValueError("Tool calls required but none provided")

            # Handle as regular message in auto mode
            return (
                self.memory.messages[-1].content or "No content or commands to execute"
            )

        results = []
        for command in self.commands:
            result = await self._execute_tool_call(command)
            logger.info(result)

            # Add tool response to memory
            tool_msg = Message.tool_message(
                content=result, tool_call_id=command.id, name=command.function.name
            )
            self.memory.add_message(tool_msg)
            results.append(result)

        return "\n\n".join(results)

    async def _execute_tool_call(self, command: ToolCall) -> str:
        """Execute a single tool call and return formatted result"""
        try:
            if not command.function.name:
                raise ValueError("No command specified")

            cmd_name = command.function.name
            if cmd_name not in self.tool_collection.tool_map:
                raise ValueError(f"Command '{cmd_name}' not found")

            args = json.loads(command.function.arguments)
            result = await self.tool_collection.execute(name=cmd_name, tool_input=args)

            observation = (
                f"Observed result of cmd executed:\n{result}"
                if result
                else "Cmd completed with no output"
            )
            if self._is_special_tool(name=cmd_name):
                self.state = AgentState.FINISHED

            return observation

        except json.JSONDecodeError:
            raise ToolError("Invalid tool arguments format")
        except Exception as e:
            raise ToolError(f"Tool execution failed: {str(e)}")

    def _is_special_tool(self, name: str) -> bool:
        """Check if command is a special tool that affects agent state"""
        return name.lower() in self.special_tools
