import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar, List, Optional, Set

from app.tool.tool import Tool


# Constants
FILES_LIMIT = 250
TIMEOUT_SECONDS = 10


@dataclass
class ListFilesOutput:
    """Output class for ListFiles tool containing the list of found files."""

    files: List[Path]
    limit_reached: bool

    def to_string(self, relative_to: Optional[Path] = None) -> str:
        """Convert the file list to a formatted string.

        Args:
            relative_to: Optional path to make all paths relative to
        """
        if not self.files:
            return "No files found."

        # Convert paths to relative if base path provided
        paths = [
            str(f.relative_to(relative_to) if relative_to else f)
            for f in sorted(self.files)
        ]

        # Format output
        output = "\n".join(f"- {path}" for path in paths)
        if self.limit_reached:
            output += f"\n\nNote: File limit ({FILES_LIMIT}) reached. Some files may not be shown."

        return output


class ListFiles(Tool):
    name: ClassVar[str] = "list_files"
    description: ClassVar[
        str
    ] = """
    List files and directories within the specified directory.
    If recursive is true, it will list all files and directories recursively.
    If recursive is false, it will only list the top-level contents.
    Do not use this tool to confirm the existence of files you may have created.
    """
    parameters: ClassVar[dict] = {
        "type": "object",
        "properties": {
            "directory_path": {
                "type": "string",
                "description": "(required) The absolute path of the directory to list contents for.",
            },
            "recursive": {
                "type": "boolean",
                "description": "(required) Whether to list files recursively.",
            },
        },
        "required": ["directory_path", "recursive"],
    }

    @staticmethod
    def is_root_or_home(dir_path: Path) -> bool:
        """Check if the given path is root or home directory."""
        root = Path(os.path.abspath(os.sep))
        home = Path.home()
        return dir_path in (root, home)

    @staticmethod
    def should_ignore(path: Path, ignore_patterns: Set[str]) -> bool:
        """Check if the path should be ignored based on patterns."""
        return any(part in ignore_patterns for part in path.parts)

    async def execute(self, directory_path: str, recursive: bool) -> str:
        """Execute the list_files tool with given parameters."""
        dir_path = Path(directory_path).resolve()

        # Check for root/home directory
        if self.is_root_or_home(dir_path):
            return f"Access denied: Cannot list {dir_path} (root or home directory)"

        # Initialize variables
        results: List[Path] = []
        start_time = time.time()
        queue: List[Path] = [dir_path]
        visited: Set[Path] = set()

        # Common directories to ignore
        ignore_patterns = {
            "node_modules",
            "__pycache__",
            "env",
            "venv",
            "target",
            ".target",
            "build",
            "dist",
            "out",
            "bundle",
            "vendor",
            "tmp",
            "temp",
            "deps",
            "pkg",
        }

        while queue and len(results) < FILES_LIMIT:
            # Check timeout
            if time.time() - start_time > TIMEOUT_SECONDS:
                output = ListFilesOutput(files=results, limit_reached=True)
                return output.to_string(relative_to=dir_path)

            current_dir = queue.pop(0)
            if current_dir in visited:
                continue

            visited.add(current_dir)

            try:
                for entry in os.scandir(current_dir):
                    if len(results) >= FILES_LIMIT:
                        output = ListFilesOutput(files=results, limit_reached=True)
                        return output.to_string(relative_to=dir_path)

                    entry_path = Path(entry.path)

                    # Skip if should be ignored
                    if self.should_ignore(entry_path, ignore_patterns):
                        continue

                    # Add to results if not the root directory
                    if entry_path != dir_path:
                        results.append(entry_path)

                    # Add directory to queue if recursive
                    if recursive and entry.is_dir() and not entry.name.startswith("."):
                        queue.append(entry_path)

            except PermissionError:
                continue
            except OSError:
                continue

        output = ListFilesOutput(
            files=results, limit_reached=len(results) >= FILES_LIMIT
        )
        return output.to_string(relative_to=dir_path)
