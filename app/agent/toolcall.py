import json
from typing import Any, List, Literal, Optional

from pydantic import Field

from app.agent.react import ReActAgent
from app.logger import logger
from app.prompt.toolcall import NEXT_STEP_PROMPT, SYSTEM_PROMPT
from app.schema import AgentState, Message, ToolCall
from app.tool import CreateChatCompletion, Terminate, ToolCollection

NO_TOOL_CALL_REQUIRED = "No tool call required"
TOOL_CALL_REQUIRED = "Tool calls required but none provided"


class ToolCallAgent(ReActAgent):
    """Base agent class for handling tool/function calls with enhanced abstraction"""

    name: str = "toolcall"
    description: str = "an agent that can execute tool calls."

    system_prompt: str = SYSTEM_PROMPT
    next_step_prompt: str = NEXT_STEP_PROMPT

    available_tools: ToolCollection = ToolCollection(
        CreateChatCompletion(), Terminate()
    )
    tool_choices: Literal["none", "auto", "required"] = "auto"
    special_tool_names: List[str] = Field(default_factory=lambda: [Terminate().name])

    tool_calls: List[ToolCall] = Field(default_factory=list)

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

    async def run(self, requirement: Optional[str] = None) -> str:
        """Main execution loop"""
        if requirement:
            # Put user message at the top of the memory
            self.memory.messages.insert(0, Message.user_message(requirement))

        results = []
        async with self.state_context(AgentState.RUNNING):
            while self.current_step < self.max_steps:
                self.current_step += 1

                # Execute a step
                result = await self.step()
                if result == NO_TOOL_CALL_REQUIRED:
                    if self.tool_choices == "required":
                        raise ValueError(TOOL_CALL_REQUIRED)
                    results.append(result)
                    break

                # Check for stuck state
                if self.is_stuck():
                    self.handle_stuck_state()

                results.append(f"Step {self.current_step}: {result}")

                if self.state == AgentState.FINISHED:
                    break

            return "\n".join(results)

    async def step(self) -> str:
        """Execute a single step: think and act."""
        should_act = await self.think()
        if not should_act:
            return NO_TOOL_CALL_REQUIRED

        result = await self.act()
        return result

    async def think(self) -> bool:
        """Process current state and decide next actions using tools"""
        messages = self.memory.messages
        if self.next_step_prompt:
            user_msg = Message.user_message(self.next_step_prompt)
            messages = messages + [user_msg]

        response = await self.llm.ask_tool(
            messages=messages,
            system_msgs=Message.system_message(self.system_prompt) if self.system_prompt else None,
            tools=self.available_tools.to_params(),
            tool_choice=self.tool_choices,
        )
        self.tool_calls = response.tool_calls

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
            Message.from_tool_calls(
                content=response.content, tool_calls=self.tool_calls
            )
            if self.tool_calls
            else Message.assistant_message(response.content)
        )
        self.memory.add_message(assistant_msg)

        if self.tool_choices == "required" and not self.tool_calls:
            return True  # Will be handled in run()

        # For 'auto' mode, continue with content if no commands but content exists
        if self.tool_choices == "auto" and not self.tool_calls:
            return bool(response.content)

        return bool(self.tool_calls)

    async def act(self) -> str:
        """Execute tool calls and handle their results"""
        if not self.tool_calls:
            if self.tool_choices == "required":
                raise ValueError(TOOL_CALL_REQUIRED)

            # Handle as regular message in auto mode
            return (
                self.memory.messages[-1].content or "No content or commands to execute"
            )

        results = []
        for command in self.tool_calls:
            result = await self.execute_tool(command)
            logger.info(result)

            # Add tool response to memory
            tool_msg = Message.tool_message(
                content=result, tool_call_id=command.id, name=command.function.name
            )
            self.memory.add_message(tool_msg)
            results.append(result)

        return "\n\n".join(results)

    async def execute_tool(self, command: ToolCall) -> str:
        """Execute a single tool call and return formatted result"""
        if not command.function.name:
            raise ValueError("No command specified")

        name = command.function.name
        if name not in self.available_tools.tool_map:
            raise ValueError(f"Command '{name}' not found")

        args = json.loads(command.function.arguments)
        result = await self.available_tools.execute(name=name, tool_input=args)

        observation = (
            f"Observed output of cmd `{name}` executed:\n{str(result)}"
            if result
            else "Cmd completed with no output"
        )
        await self._handle_special_tool(name=name, result=result)

        return observation

    async def _handle_special_tool(self, name: str, result: Any, **kwargs):
        """Handle special tool execution and state changes"""
        if not self._is_special_tool(name):
            return

        if self._should_finish_execution(name=name, result=result, **kwargs):
            self.state = AgentState.FINISHED

    @staticmethod
    def _should_finish_execution(**kwargs) -> bool:
        """Determine if tool execution should finish the agent"""
        return True

    def _is_special_tool(self, name: str) -> bool:
        """Check if command is a special tool that affects agent state"""
        return name.lower() in self.special_tool_names
