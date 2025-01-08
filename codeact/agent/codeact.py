from codeact.action.execute_bash import ExecuteBash
from codeact.agent.base import BaseAgent
from codeact.logger import logger
from codeact.schema import AgentState, Message

from openhands_aci import file_editor

from codeact.prompts.function_calling import get_tools
from codeact.prompts.prompts import SYSTEM_PROMPT, NEXT_STEP_PROMPT

from typing import Dict, List
from pydantic import Field, model_validator
import inspect
import traceback

from codeact.utils import transform_tool_call_to_command, parse_oh_aci_output


class CodeActAgent(BaseAgent):
    """An agent that implements the CodeActAgent paradigm for executing code and natural conversations."""
    name: str = "CodeActAgent"
    description: str = "an autonomous AI programmer that interacts directly with the computer to solve tasks."

    system_prompt: str = SYSTEM_PROMPT
    next_step_prompt: str = NEXT_STEP_PROMPT

    tools: List[str] = get_tools(return_tool_names=True)
    tool_execution_map: Dict[str, callable] = Field(default_factory=dict)
    special_tool_commands: List[str] = Field(default_factory=lambda: ["finish"])

    max_react_loop: int = 30
    commands: List[dict] = Field(default_factory=list)

    bash: ExecuteBash = Field(default_factory=ExecuteBash)
    working_dir: str = ""

    @model_validator(mode="after")
    def set_tool_execution(self) -> "CodeActAgent":
        """Update available tools and their execution methods"""
        self.tool_execution_map = {
            "execute_bash": self.bash.run,
            "str_replace_editor": file_editor,
            "finish": self._finish,
        }
        return self

    async def think(self) -> bool:
        """Process current state and decide next action"""
        if not self.tools:
            return False

        # Update working directory
        self.working_dir = await self.bash.run("pwd")

        messages = self.memory.messages
        if self.next_step_prompt:
            user_msg = Message(role="user", content=self.next_step_prompt.format(current_dir=self.working_dir))
            messages = messages + [user_msg]

        response = await self.llm.aask_function(
            messages=messages,
            tools=self.get_tool_param(),
            system_msgs=[self.system_prompt]
        )

        logger.info(f"Tool content: {response.content}")
        logger.info(f"Tool calls: {response.tool_calls}")

        # Update state and memory
        self.commands = response.tool_calls or []

        # Create and add assistant message
        assistant_msg = Message.from_tool_calls(
            content=response.content,
            tool_calls=response.tool_calls
        )
        self.memory.add_message(assistant_msg)

        return bool(self.commands)

    async def act(self) -> str:
        """Execute decided actions"""
        if not self.commands:
            return "No actions to execute"

        outputs = []
        for command in self.commands:
            try:
                output = await self._run_command(transform_tool_call_to_command(command))
            except Exception as e:
                output = f"Command execution failed: {str(e)}"
            logger.info(f"Command output: {output}")
            tool_msg = Message.tool_message(
                content=output,
                tool_call_id=command.id,
                name=command.function.name
            )
            # Add tool response to memory
            self.memory.add_message(tool_msg)
            outputs.append(output)

        return "\n\n".join(outputs)

    async def _run_command(self, cmd: dict) -> str:
        """Execute a single command"""
        cmd_name = cmd["command"]
        output = f"Command {cmd_name} executed"

        # Execute normal command
        if cmd_name in self.tool_execution_map:
            tool_obj = self.tool_execution_map[cmd_name]
            try:
                if inspect.iscoroutinefunction(tool_obj):
                    result = await tool_obj(**cmd["args"])
                else:
                    result = tool_obj(**cmd["args"])

                if result:
                    output += f": {str(result)}" if cmd_name != "str_replace_editor" else parse_oh_aci_output(result)
                return output
            except Exception:
                tb = traceback.format_exc()
                return output + f": {tb}"

        return f"Command {cmd_name} not found."

    async def _finish(self, message: str = "") -> str:
        """Finish the current execution"""
        self.state = AgentState.FINISHED
        return message or "Execution completed"

    @staticmethod
    def get_tool_param() -> List[dict]:
        """Get tool parameters"""
        return get_tools(return_tool_names=False)
