import inspect
import traceback
from typing import Dict, List

from openai.types.chat import ChatCompletionToolParam
from pydantic import Field, model_validator

from app.agent.base import BaseAgent
from app.logger import logger
from app.schema import AgentState, Message
from app.tool.tool import Tool
from app.utils import transform_tool_call_to_command


class ToolCallAgent(BaseAgent):
    """Base agent class for handling tool/function calls with enhanced abstraction"""

    tools: List[Tool] = Field(default_factory=list)
    tool_execution_map: Dict[str, callable] = Field(default_factory=dict)
    special_tool_commands: List[str] = Field(default_factory=lambda: ["finish"])
    commands: List[dict] = Field(default_factory=list)

    max_steps: int = 30

    @model_validator(mode="after")
    def initialize_tool_execution_map(self) -> "ToolCallAgent":
        """Initialize tool execution map from provided tools"""
        for tool_cls in self.tools:
            self.tool_execution_map[tool_cls.name] = tool_cls().execute
        return self

    async def think(self) -> bool:
        """Process current state and decide next actions using tools"""
        messages = self.memory.messages
        if self.next_step_prompt:
            user_msg = Message(
                role="user",
                content=self.next_step_prompt,
            )
            messages = messages + [user_msg]

        response = await self.llm.aask_function(
            messages=messages,
            tools=self.get_tool_params(),
            system_msgs=[self.system_prompt],
        )

        logger.info(f"Tool content: {response.content}")
        logger.info(f"Tool calls: {response.tool_calls}")

        # Update state and memory
        self.commands = response.tool_calls

        # Create and add assistant message
        assistant_msg = Message.from_tool_calls(
            content=response.content, tool_calls=self.commands
        )
        self.memory.add_message(assistant_msg)

        return bool(self.commands)

    async def act(self) -> str:
        """Execute tool calls and handle their results"""
        if not self.commands:
            return "No commands to execute"

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

    async def _execute_tool_call(self, command: dict) -> str:
        """Execute a single tool call and return formatted result"""
        cmd = transform_tool_call_to_command(command)
        cmd_name = cmd.get("command")
        args = cmd.get("arguments", {})

        if not cmd_name:
            return "Error:\nNo command specified."

        if cmd_name not in self.tool_execution_map:
            return f"Error:\nCommand '{cmd_name}' not found."

        tool_executor = self.tool_execution_map[cmd_name]

        try:
            if inspect.iscoroutinefunction(tool_executor):
                result = await tool_executor(**args)
            else:
                result = tool_executor(**args)

            observation = f"Observed result of {cmd_name}:\n{str(result) if result else 'Command completed successfully with no output.'}"

            if self._is_special_command(cmd):
                self.state = AgentState.FINISHED

            return observation

        except Exception:
            return f"Error:\n{traceback.format_exc()}"

    def _is_special_command(self, cmd: dict) -> bool:
        """Check if command is a special command that affects agent state"""
        return cmd["command"] in self.special_tool_commands

    def get_tool_params(self) -> List[ChatCompletionToolParam]:
        """Get tool parameters for LLM function calling"""
        return [tool.to_tool_param() for tool in self.tools]
