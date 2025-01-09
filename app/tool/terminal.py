import asyncio
from typing import Any, ClassVar, Dict, Optional, Union
from uuid import uuid4

import aiohttp
from pydantic import BaseModel, Field

from app.tool.tool import Tool


class TerminalInputPartial(BaseModel):
    """Model for terminal command input without editor URL."""

    command: str = Field(..., description="The CLI command to execute")

    def sanitize_for_repro_script(self) -> "TerminalInputPartial":
        """Sanitize command for reproduction script."""
        if "reproduce_error.py" in self.command and "python" in self.command:
            return TerminalInputPartial(command="python reproduce_error.py")
        return self

    def to_string(self) -> str:
        """Convert command to string format."""
        return f"""<execute_command>
<command>
{self.command}
</command>
</execute_command>"""

    @classmethod
    def schema_json(cls, **kwargs) -> Dict[str, Any]:
        """Generate JSON schema for the command."""
        return {
            "name": "execute_command",
            "description": "Request to execute a CLI command on the system. Commands will be executed in the current working directory.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "(required) The CLI command to execute. This should be valid for the current operating system. Ensure proper formatting and safety.",
                    }
                },
                "required": ["command"],
            },
        }


class TerminalInput(BaseModel):
    """Complete terminal input including editor URL."""

    command: str
    editor_url: str
    tool_use_id: str = Field(default_factory=lambda: f"toolu_{uuid4().hex}")


class TerminalOutput(BaseModel):
    """Model for terminal command output."""

    output: str
    tool_use_id: str
    status: str = "completed"
    error: Optional[str] = None


class ActionToolInputPartial(BaseModel):
    """Model for tool input with ID."""

    tool_use_id: str = Field(default_factory=lambda: f"toolu_{uuid4().hex}")
    tool_input_partial: TerminalInputPartial

    def __str__(self) -> str:
        return f'Tool(ActionToolInputPartial {{ tool_use_id: "{self.tool_use_id}", tool_input_partial: TerminalCommand({self.tool_input_partial}) }})'


class Terminal(Tool):
    name: ClassVar[str] = "execute_command"
    description: ClassVar[
        str
    ] = """Request to execute a CLI command on the system.
Use this when you need to perform system operations or run specific commands to accomplish any step in the user's task.
You must tailor your command to the user's system and provide a clear explanation of what the command does.
Prefer to execute complex CLI commands over creating executable scripts, as they are more flexible and easier to run.
Commands will be executed in the current working directory.
Note: Append `sleep 0.05` to commands completing under 50ms to ensure output capture.
"""
    parameters: ClassVar[dict] = TerminalInputPartial.schema_json()["input_schema"]
    session: aiohttp.ClientSession = None
    _current_tool_use_id: Optional[str] = None

    def __init__(self, /, **data: Any):
        """Initialize the terminal tool with an aiohttp session."""
        super().__init__(**data)
        self.session = aiohttp.ClientSession()
        self._current_tool_use_id: Optional[str] = None

    @property
    def current_tool_use_id(self) -> Optional[str]:
        """Get the current tool use ID."""
        return self._current_tool_use_id

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.session.close()

    async def execute(
        self,
        command: Union[str, TerminalInputPartial],
        editor_url: Optional[str] = None,
    ) -> TerminalOutput:
        """Execute a terminal command."""
        if not editor_url:
            raise ValueError("Editor URL is required")

        # Handle different input types
        if isinstance(command, str):
            command_str = command
        elif isinstance(command, TerminalInputPartial):
            command_str = command.command
        else:
            raise ValueError(f"Unsupported command type: {type(command)}")

        # Create terminal input with tool use ID
        terminal_input = TerminalInput(
            command=command_str,
            editor_url=editor_url,
            tool_use_id=self._current_tool_use_id or f"toolu_{uuid4().hex}",
        )

        try:
            async with self.session.post(
                f"{editor_url}/execute_terminal_command",
                json=terminal_input.model_dump(),
            ) as response:
                if response.status != 200:
                    error_msg = await response.text()
                    return TerminalOutput(
                        output="",
                        tool_use_id=terminal_input.tool_use_id,
                        status="failed",
                        error=f"Failed to execute command: {error_msg}",
                    )

                result = await response.json()
                return TerminalOutput(
                    output=result.get("output", "No output received"),
                    tool_use_id=terminal_input.tool_use_id,
                    status="completed",
                )

        except Exception as e:
            return TerminalOutput(
                output="",
                tool_use_id=terminal_input.tool_use_id,
                status="failed",
                error=f"Error executing terminal command: {str(e)}",
            )

    @classmethod
    async def example_usage(cls) -> None:
        """Demonstrate example usage of the terminal tool."""
        async with TerminalTool() as tool:
            # Example 1: Simple string command
            command1 = "python reproduce_error.py"
            result1 = await tool.execute(command1, editor_url="http://localhost:8000")
            print(f"Example 1 output: {result1}")

            # Example 2: Using TerminalInputPartial
            command2 = TerminalInputPartial(command="ls -la")
            result2 = await tool.execute(command2, editor_url="http://localhost:8000")
            print(f"Example 2 output: {result2}")

            # Example 3: Using ActionToolInputPartial
            action_input = ActionToolInputPartial(
                tool_input_partial=TerminalInputPartial(command="echo 'Hello World'")
            )
            tool._current_tool_use_id = action_input.tool_use_id
            result3 = await tool.execute(
                action_input.tool_input_partial, editor_url="http://localhost:8000"
            )
            print(f"Example 3 output: {result3}")


if __name__ == "__main__":
    # Run example usage
    asyncio.run(TerminalTool.example_usage())
