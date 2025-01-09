import inspect
from typing import Dict, List

from openai.types.chat import ChatCompletionToolParam
from pydantic import Field, model_validator

from app.agent.base import BaseAgent
from app.logger import logger
from app.prompts.codeact import NEXT_STEP_TEMPLATE, SYSTEM_PROMPT
from app.schema import AgentState, Message
from app.tool.bash import Bash
from app.tool.finish import Finish
from app.tool.str_replace_editor import StrReplaceEditor
from app.tool.tool import Tool
from app.utils import transform_tool_call_to_command


class CodeActAgent(BaseAgent):
    """An agent that implements the CodeActAgent paradigm for executing code and natural conversations."""

    name: str = "CodeActAgent"
    description: str = "an autonomous AI programmer that interacts directly with the computer to solve tasks."

    system_prompt: str = SYSTEM_PROMPT
    next_step_prompt: str = NEXT_STEP_TEMPLATE

    bash: Bash = Field(default_factory=Bash)
    tools: List[Tool] = [Bash, StrReplaceEditor, Finish]
    tool_execution_map: Dict[str, callable] = Field(default_factory=dict)
    special_tool_commands: List[str] = Field(default_factory=lambda: ["finish"])
    commands: List[dict] = Field(default_factory=list)

    working_dir: str = ""

    max_react_loop: int = 30

    @model_validator(mode="after")
    def set_tool_execution_map(self) -> "CodeActAgent":
        """Update available tools and their execution methods"""
        for tool_cls in self.tools:
            tool_ins = tool_cls()
            self.tool_execution_map[tool_cls.name] = tool_ins.execute
        return self

    async def think(self) -> bool:
        """Process current state and decide next action"""
        # Update working directory
        self.working_dir = await self.bash.execute("pwd")

        messages = self.memory.messages
        if self.next_step_prompt:
            user_msg = Message(
                role="user",
                content=self.next_step_prompt.format(current_dir=self.working_dir),
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
        self.commands = response.tool_calls or []

        # Create and add assistant message
        assistant_msg = Message.from_tool_calls(
            content=response.content, tool_calls=response.tool_calls
        )
        self.memory.add_message(assistant_msg)

        return bool(self.commands)

    async def act(self) -> str:
        """Execute decided commands"""
        if not self.commands:
            return "No commands to execute"

        outputs = []
        for command in self.commands:
            output = await self._run_command(transform_tool_call_to_command(command))
            logger.info(output)
            tool_msg = Message.tool_message(
                content=output, tool_call_id=command.id, name=command.function.name
            )
            # Add tool response to memory
            self.memory.add_message(tool_msg)
            outputs.append(output)

        return "\n\n".join(outputs)

    async def _run_command(self, cmd: dict) -> str:
        """Execute a single command"""
        cmd_name = cmd["command"]
        output = "Observation:\n"

        # Execute command
        if cmd_name in self.tool_execution_map:
            tool_obj = self.tool_execution_map[cmd_name]
            if inspect.iscoroutinefunction(tool_obj):
                result = await tool_obj(**cmd["args"])
            else:
                result = tool_obj(**cmd["args"])

            if result:
                output += str(result)

            # Check special command to update state
            if self._is_special_command(cmd):
                self.state = AgentState.FINISHED

            return output

        return f"Command {cmd_name} not found."

    def _is_special_command(self, cmd) -> bool:
        return cmd["command"] in self.special_tool_commands

    def get_tool_params(self) -> List[ChatCompletionToolParam]:
        """Get tool parameters"""
        return [tool.to_tool_param() for tool in self.tools]
