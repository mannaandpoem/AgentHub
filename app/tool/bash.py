import subprocess
from pathlib import Path
from typing import ClassVar, Dict, List, Optional, Tuple, Union

from app.tool.tool import Tool


_BASH_DESCRIPTION = """Execute a bash command in the terminal.
* Long running commands: For commands that may run indefinitely, it should be run in the background and the output should be redirected to a file, e.g. command = `python3 app.py > server.log 2>&1 &`.
* Interactive: If a bash command returns exit code `-1`, this means the process is not yet finished. The assistant must then send a second call to terminal with an empty `command` (which will retrieve any additional logs), or it can send additional text (set `command` to the text) to STDIN of the running process, or it can send command=`ctrl+c` to interrupt the process.
* Timeout: If a command execution result says "Command timed out. Sending SIGINT to the process", the assistant should retry running the command in the background.
"""


class Bash(Tool):
    """A tool for executing bash commands"""

    name: ClassVar[str] = "bash"
    description: ClassVar[str] = "A tool for executing bash commands"
    parameters: ClassVar[dict] = {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "The bash command to execute. Can be empty to view additional logs when previous exit code is `-1`. Can be `ctrl+c` to interrupt the currently running process.",
            },
        },
        "required": ["command"],
    }

    async def execute(
        self,
        command: Union[List[str], str],
        cwd: Optional[Union[str, Path]] = None,
        env: Optional[Dict] = None,
        timeout: int = 600,
        return_string: bool = True,
    ) -> Union[str, Tuple[str, str, int]]:
        """
        Execute a command asynchronously and return its output.

        Args:
            command (Union[List[str], str]): The command to execute and its arguments.
            cwd (Optional[Union[str, Path]]): The working directory for the command.
            env (Optional[Dict]): Environment variables for the command.
            timeout (int): Timeout in seconds. Defaults to 600.
            return_string (bool): If True, returns formatted string output. Defaults to True.

        Returns:
            Union[str, Tuple[str, str, int]]: Command output as string or tuple of (stdout, stderr, returncode)
        """
        cwd = str(cwd) if cwd else None
        shell = isinstance(command, str)

        try:
            result = subprocess.run(
                command,
                cwd=cwd,
                capture_output=True,
                text=True,
                env=env,
                timeout=timeout,
                shell=shell,
            )

            if return_string:
                if result.returncode == 0 and not result.stderr:
                    return result.stdout.strip()

                output_parts = []
                if result.stdout:
                    output_parts.append(f"stdout:\n{result.stdout.strip()}")
                if result.stderr:
                    output_parts.append(f"stderr:\n{result.stderr.strip()}")
                if result.returncode != 0:
                    output_parts.append(f"return code: {result.returncode}")

                return "\n\n".join(output_parts)

            return result.stdout, result.stderr, result.returncode

        except subprocess.TimeoutExpired:
            if return_string:
                return f"Command timed out after {timeout} seconds"
            return "", f"Command timed out after {timeout} seconds", 1
        except Exception as e:
            if return_string:
                return f"Error executing command: {str(e)}"
            return "", f"Error executing command: {str(e)}", 1
