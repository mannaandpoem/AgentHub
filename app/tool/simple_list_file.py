import os
import time
from pathlib import Path
from typing import List, Set, Optional


class ListFilesResult:
    """Result class for ListFiles tool containing the list of found files."""

    def __init__(self, files: List[Path], limit_reached: bool):
        self.files = files
        self.limit_reached = limit_reached

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


class SimpleListFiles:
    name = "list_files"
    description = """
    List files and directories within the specified directory.
    This tool can traverse directories recursively and list all files.
    It is suitable for exploring filesystems but not for file existence checks.
    """

    FILES_LIMIT = 100000
    TIMEOUT_SECONDS = 10

    @staticmethod
    def is_root_or_home(dir_path: Path) -> bool:
        """Check if the given path is root or home directory."""
        root = Path(os.path.abspath(os.sep))
        home = Path.home()
        return dir_path == root or dir_path == home

    @staticmethod
    def should_ignore(path: Path, ignore_patterns: Set[str]) -> bool:
        """Check if the path should be ignored based on patterns."""
        return any(part in ignore_patterns for part in path.parts)

    @staticmethod
    def list_files(directory_path: Path, recursive: bool = True) -> ListFilesResult:
        """Execute the list_files tool with given parameters."""
        dir_path = directory_path.resolve()

        # Check for root/home directory
        if SimpleListFiles.is_root_or_home(dir_path):
            return ListFilesResult(
                files=[], limit_reached=False
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

        while queue and len(results) < SimpleListFiles.FILES_LIMIT:
            # Check timeout
            if time.time() - start_time > SimpleListFiles.TIMEOUT_SECONDS:
                return ListFilesResult(files=results, limit_reached=True)

            current_dir = queue.pop(0)
            if current_dir in visited:
                continue

            visited.add(current_dir)

            try:
                for entry in os.scandir(current_dir):
                    entry_path = Path(entry.path)

                    # Skip if should be ignored
                    if SimpleListFiles.should_ignore(entry_path, ignore_patterns):
                        continue

                    # Add files (Python files only)
                    if entry.is_file() and entry_path.suffix == ".py":
                        results.append(entry_path)

                    # Add directory to queue if recursive
                    if recursive and entry.is_dir() and not entry.name.startswith("."):
                        queue.append(entry_path)

                    # Check file limit
                    if len(results) >= SimpleListFiles.FILES_LIMIT:
                        break

            except PermissionError:
                continue
            except OSError:
                continue

        return ListFilesResult(
            files=results, limit_reached=len(results) >= SimpleListFiles.FILES_LIMIT
        )