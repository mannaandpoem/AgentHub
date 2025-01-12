import asyncio
import json
import traceback
from typing import List, Literal, Optional

from pydantic import Field

from app.agent.base import BaseAgent
from app.logger import logger
from app.prompt.toolcall import NEXT_STEP_PROMPT, SYSTEM_PROMPT
from app.schema import AgentState, Message, ToolCall
from app.tool import Bash, Finish, ToolCollection


class ToolCallAgent(BaseAgent):
    """Base agent class for handling tool/function calls with enhanced abstraction"""

    name: str = "ToolCallAgent"
    description: str = "an agent that can execute tool calls."

    system_prompt: str = SYSTEM_PROMPT
    next_step_prompt: str = NEXT_STEP_PROMPT

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
                self.current_step += 1

                try:
                    # Think phase
                    should_act = await self.think()
                    if not should_act:
                        if self.tool_choices == "required":
                            error_msg = "Error: Tool calls required but none provided"
                            self.update_memory("assistant", error_msg)
                            results.append(error_msg)
                            break
                        results.append("Thinking complete - no action needed")
                        break

                    # Check for stuck state
                    if self.is_stuck():
                        self.handle_stuck_state()

                    # Act phase
                    result = await self.act()
                    step_result = f"Step {self.current_step}: {result}"
                    results.append(step_result)

                    if self.state == AgentState.FINISHED:
                        break

                except Exception as e:
                    error_msg = f"Error in step {self.current_step}: {str(e)}"
                    logger.error(error_msg)
                    error_message = Message.assistant_message(f"Error: {error_msg}")
                    self.memory.add_message(error_message)
                    results.append(error_msg)
                    break

                await asyncio.sleep(0)

            if self.current_step >= self.max_steps:
                max_steps_msg = f"Reached maximum steps limit ({self.max_steps})"
                self.memory.add_message(Message.assistant_message(max_steps_msg))
                results.append(max_steps_msg)

        return "\n".join(results)

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

        logger.info(f"Tool content: {response.content}")
        logger.info(f"Tool calls: {response.tool_calls}")

        # Handle different tool_choices modes
        if self.tool_choices == "none":
            if response.tool_calls:
                logger.warning("Tool calls provided when tool_choice is 'none'")
            self.commands = []
            if response.content:
                self.memory.add_message(Message.assistant_message(response.content))
                return True
            return False

        # Update state and memory for 'auto' and 'required' modes
        self.commands = response.tool_calls

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
        args = json.loads(command.function.arguments)
        cmd_name = command.function.name

        if not cmd_name:
            return "Error:\nNo command specified."

        if cmd_name not in self.tool_collection.tool_map:
            return f"Error:\nCommand '{cmd_name}' not found."

        try:
            result = await self.tool_collection.execute(name=cmd_name, tool_input=args)

            observation = f"Observed result of {cmd_name}:\n{str(result) if result else 'Command completed successfully with no output.'}"

            if self._is_special_tool(name=cmd_name):
                self.state = AgentState.FINISHED

            return observation

        except Exception:
            return f"Error:\n{traceback.format_exc()}"

    def _is_special_tool(self, name: str) -> bool:
        """Check if command is a special tool that affects agent state"""
        return name.lower() in self.special_tools
