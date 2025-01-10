from typing import ClassVar, Literal, Optional

from pydantic import BaseModel

from app.tool.tool import Tool


class TerminalOutput(BaseModel):
    """Model for terminal command output."""

    output: str
    status: Literal["completed", "failed"]
    error: Optional[str] = None

    def to_string(self) -> str:
        return self.output if self.status == "completed" else f"Error: {self.error}"

    def __str__(self):
        return self.to_string()


class Terminal(Tool):
    name: ClassVar[str] = "execute_command"
    description: ClassVar[
        str
    ] = """Request to execute a CLI command on the system.
Use this when you need to perform system operations or run specific commands to accomplish any step in the user's task.
You must tailor your command to the user's system and provide a clear explanation of what the command does.
Prefer to execute complex CLI commands over creating executable scripts, as they are more flexible and easier to run.
Commands will be executed in the current working directory.
Note: You MUST append a `sleep 0.05` to the end of the command for commands that will complete in under 50ms, as this will circumvent a known issue with the terminal tool where it will sometimes not return the output when the command completes too quickly.
"""
    parameters: ClassVar[dict] = {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "(required) The CLI command to execute. This should be valid for the current operating system. Ensure the command is properly formatted and does not contain any harmful instructions.",
            }
        },
        "required": ["command"],
    }

    async def execute(self, command: str) -> str:
        """Execute a terminal command asynchronously."""
        sanitized_command = self._sanitize_command(command)
        try:
            process = await asyncio.create_subprocess_shell(
                sanitized_command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await process.communicate()
            status = "completed" if process.returncode == 0 else "failed"
            output = TerminalOutput(
                output=stdout.decode().strip(),
                status=status,
                error=stderr.decode().strip(),
            )
        except Exception as e:
            output = TerminalOutput(output="", status="failed", error=str(e))

        return output

    @staticmethod
    def _sanitize_command(command: str) -> str:
        """Sanitize the command for safe execution."""
        if "reproduce_error.py" in command and "python" in command:
            return "python reproduce_error.py"
        return command


# Example usage
async def example_usage():
    terminal = Terminal()

    # Example: Simple command execution
    result = await terminal.execute("ls -la")
    print(f"Command output: {result}")


if __name__ == "__main__":
    import asyncio

    asyncio.run(example_usage())
