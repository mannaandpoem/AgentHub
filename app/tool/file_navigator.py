import os
from typing import ClassVar, Optional

from app.tool.tool import Tool


class FileNavigator(Tool):
    name: ClassVar[str] = "file_navigator"
    description: ClassVar[str] = (
        "Provides various file manipulation capabilities such as opening files, navigating to specific lines, "
        "scrolling, and searching within files and directories."
    )
    parameters: ClassVar[dict] = {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "The command to perform.",
                "enum": [
                    "open_file",
                    "goto_line",
                    "scroll_down",
                    "scroll_up",
                    "search_dir",
                    "search_file",
                    "find_file",
                ],
            },
            "path": {
                "type": "string",
                "description": "The path to the file or directory.",
            },
            "line_number": {
                "type": "integer",
                "description": "The line number to navigate to.",
            },
            "context_lines": {
                "type": "integer",
                "description": "Number of context lines to display.",
            },
            "search_term": {
                "type": "string",
                "description": "The term to search for.",
            },
            "file_name": {
                "type": "string",
                "description": "The name of the file to find.",
            },
        },
        "required": ["command"],
    }

    # Initialize state variables
    current_file: Optional[str] = None
    current_line: int = 1
    window: int = 100

    def execute(self, **kwargs):
        command = kwargs.get("command")
        if not command:
            return {"error": "No command specified."}

        method = getattr(self, command, None)
        if not method:
            return {"error": f"Command '{command}' is not supported."}

        try:
            return method(**kwargs)
        except Exception as e:
            return {"error": str(e)}

    def open_file(self, **kwargs):
        path = kwargs.get("path")
        line_number = kwargs.get("line_number", 1)
        context_lines = kwargs.get("context_lines", self.window)

        if not path:
            return {"error": "Path is required to open a file."}

        if not os.path.isfile(path):
            return {"error": f"File '{path}' not found."}

        self.current_file = os.path.abspath(path)
        try:
            with open(self.current_file, "r") as file:
                total_lines = max(1, sum(1 for _ in file))
        except Exception as e:
            return {"error": f"Failed to open file: {e}"}

        if not isinstance(line_number, int) or not (1 <= line_number <= total_lines):
            return {"error": f"Line number must be between 1 and {total_lines}."}

        self.current_line = line_number
        self.window = min(max(context_lines, 1), 100)

        output = self._generate_window_output(
            self.current_file, self.current_line, self.window
        )
        return {"output": output}

    def goto_line(self, **kwargs):
        line_number = kwargs.get("line_number")
        if line_number is None:
            return {"error": "Line number is required for 'goto_line' command."}

        if not self._check_current_file():
            return {"error": "No file is currently open."}

        try:
            with open(self.current_file, "r") as file:
                total_lines = max(1, sum(1 for _ in file))
        except Exception as e:
            return {"error": f"Failed to read file: {e}"}

        if not isinstance(line_number, int) or not (1 <= line_number <= total_lines):
            return {"error": f"Line number must be between 1 and {total_lines}."}

        self.current_line = line_number
        output = self._generate_window_output(
            self.current_file, self.current_line, self.window
        )
        return {"output": output}

    def scroll_down(self):
        if not self._check_current_file():
            return {"error": "No file is currently open."}

        try:
            with open(self.current_file, "r") as file:
                total_lines = max(1, sum(1 for _ in file))
        except Exception as e:
            return {"error": f"Failed to read file: {e}"}

        self.current_line = min(self.current_line + self.window, total_lines)
        output = self._generate_window_output(
            self.current_file, self.current_line, self.window, ignore_window=True
        )
        return {"output": output}

    def scroll_up(self):
        if not self._check_current_file():
            return {"error": "No file is currently open."}

        self.current_line = max(self.current_line - self.window, 1)
        try:
            with open(self.current_file, "r") as file:
                total_lines = max(1, sum(1 for _ in file))
        except Exception as e:
            return {"error": f"Failed to read file: {e}"}

        self.current_line = min(self.current_line + self.window, total_lines)
        output = self._generate_window_output(
            self.current_file, self.current_line, self.window, ignore_window=True
        )
        return {"output": output}

    @staticmethod
    def search_dir(**kwargs):
        search_term = kwargs.get("search_term")
        dir_path = kwargs.get("path", "./")

        if not search_term:
            return {"error": "Search term is required for 'search_dir' command."}

        if not os.path.isdir(dir_path):
            return {"error": f"Directory '{dir_path}' not found."}

        matches = []
        try:
            for root, _, files in os.walk(dir_path):
                for file in files:
                    if file.startswith("."):
                        continue
                    file_path = os.path.join(root, file)
                    with open(file_path, "r", errors="ignore") as f:
                        for line_num, line in enumerate(f, 1):
                            if search_term in line:
                                matches.append((file_path, line_num, line.strip()))
                        continue
        except Exception as e:
            return {"error": f"Failed to search directory: {e}"}

        if not matches:
            return {"output": f'No matches found for "{search_term}" in {dir_path}'}

        num_matches = len(matches)
        num_files = len(set(match[0] for match in matches))

        if num_files > 100:
            return {
                "output": f'More than {num_files} files matched for "{search_term}" in {dir_path}. Please narrow your search.'
            }

        output = f'[Found {num_matches} matches for "{search_term}" in {dir_path}]\n'
        for file_path, line_num, line in matches:
            output += f"{file_path} (Line {line_num}): {line}\n"
        output += f'[End of matches for "{search_term}" in {dir_path}]'
        return {"output": output}

    def search_file(self, **kwargs):
        search_term = kwargs.get("search_term")
        file_path = kwargs.get("path", self.current_file)

        if not search_term:
            return {"error": "Search term is required for 'search_file' command."}

        if not file_path:
            return {"error": "No file specified or currently open."}

        if not os.path.isfile(file_path):
            return {"error": f"File '{file_path}' not found."}

        matches = []
        try:
            with open(file_path, "r") as file:
                for i, line in enumerate(file, 1):
                    if search_term in line:
                        matches.append((i, line.strip()))
        except Exception as e:
            return {"error": f"Failed to read file: {e}"}

        if matches:
            output = (
                f'[Found {len(matches)} matches for "{search_term}" in {file_path}]\n'
            )
            for line_num, line in matches:
                output += f"Line {line_num}: {line}\n"
            output += f'[End of matches for "{search_term}" in {file_path}]'
            return {"output": output}
        else:
            return {"output": f'[No matches found for "{search_term}" in {file_path}]'}

    @staticmethod
    def find_file(**kwargs):
        file_name = kwargs.get("file_name")
        dir_path = kwargs.get("path", "./")

        if not file_name:
            return {"error": "File name is required for 'find_file' command."}

        if not os.path.isdir(dir_path):
            return {"error": f"Directory '{dir_path}' not found."}

        matches = []
        try:
            for root, _, files in os.walk(dir_path):
                for file in files:
                    if file_name in file:
                        matches.append(os.path.join(root, file))
        except Exception as e:
            return {"error": f"Failed to search directory: {e}"}

        if matches:
            output = f'[Found {len(matches)} matches for "{file_name}" in {dir_path}]\n'
            for match in matches:
                output += f"{match}\n"
            output += f'[End of matches for "{file_name}" in {dir_path}]'
            return {"output": output}
        else:
            return {"output": f'[No matches found for "{file_name}" in {dir_path}]'}

    # Helper Methods

    def _check_current_file(self) -> bool:
        if not self.current_file or not os.path.isfile(self.current_file):
            return False
        return True

    @staticmethod
    def _generate_window_output(
        file_path: str, targeted_line: int, window: int, ignore_window: bool = False
    ) -> str:
        try:
            with open(file_path, "r") as file:
                content = file.read()

            if not content.endswith("\n"):
                content += "\n"

            lines = content.splitlines(True)  # Keep line endings
            total_lines = len(lines)

            clamped_line = max(1, min(targeted_line, total_lines))
            half_window = max(1, window // 2)

            if ignore_window:
                start = max(1, clamped_line)
                end = min(total_lines, clamped_line + window)
            else:
                start = max(1, clamped_line - half_window)
                end = min(total_lines, clamped_line + half_window)

            if start == 1:
                end = min(total_lines, start + window - 1)
            if end == total_lines:
                start = max(1, end - window + 1)

            output = ""
            if start > 1:
                output += f"({start - 1} more lines above)\n"
            else:
                output += "(this is the beginning of the file)\n"

            for i in range(start, end + 1):
                line_content = lines[i - 1].rstrip("\n")
                output += f"{i}|{line_content}\n"

            if end < total_lines:
                output += f"({total_lines - end} more lines below)\n"
            else:
                output += "(this is the end of the file)\n"

            if output.strip().endswith("more lines below)"):
                output += "\n[Use scroll_down to view the next 100 lines of the file!]"

            return output.strip()
        except Exception as e:
            return f"Failed to generate window output: {e}"
