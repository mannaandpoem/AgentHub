from swe.action.action import Action

from typing import Optional, Union, Dict, List, Tuple
from pathlib import Path
import subprocess


class ExecuteBash(Action):
    """Execute bash commands"""

    class Config:
        arbitrary_types_allowed = True

    async def run(
            self,
            command: Union[List[str], str],
            cwd: Optional[Union[str, Path]] = None,
            env: Optional[Dict] = None,
            timeout: int = 600,
            return_string: bool = True
    ) -> Union[str, Tuple[str, str, int]]:
        """
        Execute a command asynchronously and return its output.

        Args:
            command (Union[List[str], str]): The command to execute and its arguments.
            cwd (Optional[Union[str, Path]]): The working directory for the command.
            env (Optional[Dict]): Environment variables for the command.
            timeout (int): Timeout in seconds. Defaults to 600.
            return_string (bool): If True, returns formatted string output. Defaults to False.

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
                shell=shell
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

        except subprocess.TimeoutExpired as e:
            if return_string:
                return f"Command timed out after {timeout} seconds"
            return "", f"Command timed out after {timeout} seconds", 1
        except Exception as e:
            if return_string:
                return f"Error executing command: {str(e)}"
            return "", f"Error executing command: {str(e)}", 1