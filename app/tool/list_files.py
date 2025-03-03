import os
import time
from pathlib import Path
from typing import List, Optional, Set, Union

from pydantic import Field

from app.tool.base import BaseTool, ToolResult


# Constants
FILES_LIMIT = 100000
TIMEOUT_SECONDS = 10


class ListFilesResult(ToolResult):
    """Result class for ListFiles tool containing the list of found files."""

    files: List[Path] = Field(default_factory=list)
    limit_reached: bool = Field(default=False)

    def to_string(self, relative_to: Optional[Path] = None) -> str:
        """Convert the file list to a tree-structured string.

        Args:
            relative_to: Optional path to make all paths relative to
        """
        if not self.files:
            return "No files found."

        # Convert paths to relative if base path provided
        paths = [
            f.relative_to(relative_to) if relative_to else f
            for f in sorted(self.files)
        ]

        # Build tree structure
        tree = {}
        for path in paths:
            current = tree
            for part in path.parts:
                if part not in current:
                    current[part] = {}
                current = current[part]

        # Format output
        def format_tree(tree, indent="", is_last=True):
            lines = []
            items = list(tree.items())

            for i, (name, subtree) in enumerate(items):
                is_last_item = i == len(items) - 1
                prefix = indent + ("    " if is_last else "    ")

                if subtree:  # It's a directory
                    lines.append(f"{indent}{name}/")
                    lines.extend(format_tree(subtree, prefix, is_last_item))
                else:  # It's a file
                    lines.append(f"{indent}{name}")

            return lines

        output = "\n".join(format_tree(tree))

        if self.limit_reached:
            output += f"\n\nNote: File limit reached. Some files may not be shown."

        return output


class ListFiles(BaseTool):
    name: str = "list_files"
    description: str = """
List files and directories within the specified directory.
If recursive is true, it will list all files and directories recursively.
If recursive is false, it will only list the top-level contents.
Do not use this tool to confirm the existence of files you may have created.
"""
    parameters: dict = {
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

    files_limit: int = FILES_LIMIT

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

    async def execute(self, directory_path: Union[str, Path], recursive: bool) -> ListFilesResult:
        """Execute the list_files tool with given parameters."""
        dir_path = directory_path if isinstance(directory_path, Path) else Path(directory_path).resolve()

        # Check for root/home directory
        if self.is_root_or_home(dir_path):
            return ListFilesResult(
                error=f"Access denied: Cannot list {dir_path} (root or home directory)"
            )

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
            ".git",
            ".svn",
            '.env.miner',
            '.git',
            '.gitattributes',
            '.gitignore',
            '.idea',
            '.pre-commit-config.yaml',
            'LICENSE',
            'README.md',
        }

        while queue and len(results) < self.files_limit:
            # Check timeout
            if time.time() - start_time > TIMEOUT_SECONDS:
                result = ListFilesResult(files=results, limit_reached=True)
                return result.replace(output=result.to_string(relative_to=dir_path))

            current_dir = queue.pop(0)
            if current_dir in visited:
                continue

            visited.add(current_dir)

            try:
                for entry in os.scandir(current_dir):
                    if len(results) >= self.files_limit:
                        result = ListFilesResult(files=results, limit_reached=True)
                        return result.replace(
                            output=result.to_string(relative_to=dir_path)
                        )

                    entry_path = Path(entry.path)

                    # Skip if should be ignored
                    if self.should_ignore(entry_path, ignore_patterns):
                        continue

                    # Add to results if not the root directory
                    # It should be python file only
                    if entry_path != dir_path and entry_path.suffix == ".py":
                        results.append(entry_path)

                    # Add directory to queue if recursive
                    if recursive and entry.is_dir() and not entry.name.startswith("."):
                        queue.append(entry_path)

            except PermissionError:
                continue
            except OSError:
                continue

        result = ListFilesResult(
            files=results, limit_reached=len(results) >= self.files_limit
        )
        return result.replace(output=result.to_string(relative_to=dir_path))


if __name__ == '__main__':
    tool = ListFiles()
    import asyncio
    result = asyncio.run(tool.execute(directory_path='/Users/manna/PycharmProjects/AgentHub', recursive=True))
    print(result.output)