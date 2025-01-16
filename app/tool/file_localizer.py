import fnmatch
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field

from app.llm import LLM
from app.logger import logger
from app.tool import (
    BaseTool,
    CreateChatCompletion,
)
from .filemap import Filemap
from .list_files import ListFiles
from .tool_collection import ToolCollection
from .str_replace_editor import StrReplaceEditor

class FoundLocations:
    def __init__(self):
        self.locations: Dict[str, Any] = {}

    def add_location(self, file_path: str, code_snippets: dict):
        self.locations[file_path] = code_snippets

    def to_string(self) -> str:
        result = []
        for file_path, snippets in self.locations.items():
            result.append(f"File: {file_path}\nCode Snippets:\n{snippets}\n---")
        return "\n".join(result)


class LocationParameters(BaseModel):
    file_required: list = ["file_list"]
    file_parameters: dict = {
        "type": "object",
        "properties": {
            "file_list": {
                "type": "array",
                "description": "(required) The list of file absolute paths (2-5 files)  that may contain the issue",
            },
        },
        "required": file_required,
    }
    max_files: int = 5

    code_snippet_required: list = ["code", "line_start", "line_end"]
    code_snippet_parameters: dict = {
        "type": "object",
        "properties": {
            "code": {
                "type": "string",
                "description": "(required) The exact code snippet that contains the potential issue, including the complete function or code block (1-3 snippets)",
            },
            "description": {
                "type": "string",
                "description": "A detailed description of why this code snippet is problematic and what specific issue it contains",
            },
            "line_start": {
                "type": "integer",
                "description": "(required) The starting line number in the file where this problematic code snippet begins",
            },
            "line_end": {
                "type": "integer",
                "description": "(required) The ending line number in the file where this problematic code snippet ends",
            },
        },
        "required": code_snippet_required,
    }

    max_snippets_per_file: int = 3


class FileLocalizer(BaseTool):
    name: str = "file_localizer"
    description: str = "Locate suspicious files and code snippets in a codebase given an issue description or software development requirement."
    parameters: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "root_directory": {
                "type": "string",
                "description": "(required) The absolute path of the root directory to start the search from. Must start with '/'.",
            },
            "regex_pattern": {
                "type": "array",
                "items": {"type": "string"},
                "description": "(required) List of regular expressions to search for file contents by using Python regex syntax. Only files containing matches will be included.",
            },
            "file_patterns": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of file patterns to match (e.g., ['*.py']). If empty, defaults to Python files.",
            },
            "exclude_patterns": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of patterns to exclude (e.g., ['test_*', '*_test.py'])",
            },
        },
        "required": ["root_directory", "regex_pattern"],
    }

    list_files_tool: ListFiles = Field(default_factory=ListFiles)
    filemap_tool: Filemap = Field(default_factory=Filemap)
    editor_tool: StrReplaceEditor = Field(default_factory=StrReplaceEditor)
    tool_collection: ToolCollection = ToolCollection(CreateChatCompletion())
    llm: LLM = Field(default_factory=LLM)

    location_parameters: LocationParameters = LocationParameters()
    found_locations: FoundLocations = FoundLocations()

    development_requirement: str = Field(
        default="",
        description="The development requirement or issue description to localize in the codebase.",
    )

    async def execute(self, **kwargs) -> Any:
        """
        Execute the localization process and return found locations with code snippets.
        """
        # Validate root directory is absolute
        root_dir = kwargs["root_directory"]
        if not root_dir.startswith("/"):
            raise ValueError(
                "root_directory must be an absolute path starting with '/'"
            )

        self.development_requirement = self.development_requirement or kwargs.get(
            "development_requirement", ""
        )
        if not self.development_requirement:
            raise ValueError("development_requirement must be provided")

        recursive = kwargs.get("recursive", True)
        file_patterns = kwargs.get("file_patterns", ["*.py"])
        exclude_patterns = kwargs.get("exclude_patterns", [])
        regex_pattern = kwargs.get("regex_pattern", [])

        max_files = kwargs.get("max_files", self.location_parameters.max_files)
        max_snippets_per_file = kwargs.get(
            "max_snippets_per_file", self.location_parameters.max_snippets_per_file
        )

        # Validate max_files and max_snippets_per_file
        if not (2 <= max_files <= 5):
            raise ValueError("max_files must be between 2 and 5")
        if not (1 <= max_snippets_per_file <= 3):
            raise ValueError("max_snippets_per_file must be between 1 and 3")

        # Step 1: List all relevant files using ListFiles tool
        files_result = await self.list_files_tool.execute(
            directory_path=root_dir, recursive=recursive
        )

        found_files = await self._filter_files(
            files_result.files, file_patterns, exclude_patterns, regex_pattern
        )

        # Step 2: First LLM call to identify suspicious files
        suspicious_files = await self._identify_suspicious_files(found_files)

        # Ensure we don't exceed max_files
        suspicious_files = suspicious_files[:max_files]

        # Step 3: Second LLM call to locate specific code snippets
        await self._locate_code_snippets(suspicious_files, max_snippets_per_file)

        return self.found_locations.to_string()

    async def execute_tool(self, suspicious_files_prompt):
        response = await self.llm.ask_tool(
            messages=[{"role": "user", "content": suspicious_files_prompt}],
            tools=self.tool_collection.to_params(),
            tool_choice="required",
        )
        tool = response.tool_calls[0]
        cmd_name = tool.function.name
        logger.info(f"Executing tool: {tool}")
        if cmd_name not in self.tool_collection.tool_map:
            raise ValueError(f"Command '{cmd_name}' not found")
        args = json.loads(tool.function.arguments)
        result = await self.tool_collection.execute(name=cmd_name, tool_input=args)
        return result

    async def _identify_suspicious_files(self, files: List[str]) -> List[str]:
        """First LLM call to identify suspicious files."""
        suspicious_files_prompt = f"Given the following development requirement or issue description: {self.development_requirement}\n"

        create_chat_completion_tool = self.tool_collection.get_tool(
            "create_chat_completion"
        )
        create_chat_completion_tool.description = f"{self.description} by using LLM."
        create_chat_completion_tool.parameters = (
            self.location_parameters.file_parameters
        )
        create_chat_completion_tool.response_type = List[str]
        create_chat_completion_tool.required = self.location_parameters.file_required

        all_file_content = []
        for file_path in files:
            # Get file content using Filemap
            file_content = await self.filemap_tool.execute(file_path=file_path)
            all_file_content.append(f"---{file_path}\n{file_content}\n")

        suspicious_files_prompt += (
            "\n".join(all_file_content)
            + "\nPlease select the files that may contain the issue."
        )

        result = await self.execute_tool(suspicious_files_prompt)
        logger.info(f"Suspicious files identified: {result}")
        return result

    async def _locate_code_snippets(
        self, suspicious_files: List[str], max_snippets_per_file: int
    ):
        """Second LLM call to locate specific code snippets."""
        create_chat_completion_tool = self.tool_collection.get_tool(
            "create_chat_completion"
        )
        create_chat_completion_tool.description = f"{self.description} by using LLM."
        create_chat_completion_tool.parameters = (
            self.location_parameters.code_snippet_parameters
        )
        create_chat_completion_tool.response_type = dict
        create_chat_completion_tool.required = (
            self.location_parameters.code_snippet_required
        )
        for file_path in suspicious_files:
            # Read the file content
            file_content = await self.editor_tool.execute(
                path=file_path, command="view"
            )
            # Prepare prompt for code snippet identification
            snippet_prompt = (
                f"Given this issue description or development requirement: {self.development_requirement}\n"
                f"Please identify up to {max_snippets_per_file} code snippets.\n"
                f"{file_content}"
            )

            # Execute LLM tool to locate code snippets
            result = await self.execute_tool(snippet_prompt)
            # Ensure we don't exceed max_snippets_per_file
            if isinstance(result, list):
                result = result[:max_snippets_per_file]
            logger.info(f"Code snippets located: \n{result}")
            self.found_locations.add_location(file_path, result)

    @staticmethod
    def _is_regex_pattern(pattern: str) -> bool:
        """Check if the pattern is a regex pattern."""
        return pattern.startswith("regex:")

    @staticmethod
    def _matches_pattern(file_name: str, pattern: str) -> bool:
        """Check if file_name matches the pattern (either glob or regex)."""
        if FileLocalizer._is_regex_pattern(pattern):
            # Remove the 'regex:' prefix and compile the pattern
            regex_pattern = re.compile(pattern[6:])
            return bool(regex_pattern.match(file_name))
        return fnmatch.fnmatch(file_name, pattern)

    async def _filter_files(
        self,
        files: List[Union[str, Path]],
        include_patterns: List[str],
        exclude_patterns: List[str],
        regex_pattern: Optional[List[str]] = None,
    ) -> List[str]:
        """
        Filter files based on include and exclude patterns, and optionally content.

        Args:
            files: List of file paths
            include_patterns: List of patterns to include (glob or regex)
            exclude_patterns: List of patterns to exclude (glob or regex)
            regex_pattern: List of regex patterns to filter file contents
        """
        filtered_files = []

        for file_path in files:
            file_name = (
                file_path.strip() if isinstance(file_path, str) else str(file_path)
            )
            if not file_name:
                continue

            # Check include patterns
            included = any(
                self._matches_pattern(file_name, pattern)
                for pattern in include_patterns
            )

            # Check exclude patterns
            excluded = any(
                self._matches_pattern(file_name, pattern)
                for pattern in exclude_patterns
            )

            if included and not excluded:
                # If content filters are specified, check file contents
                if regex_pattern:
                    file_content = await self.filemap_tool.execute(file_path=file_name)
                    content_matched = False
                    for pattern in regex_pattern:
                        if re.search(pattern, file_content):
                            content_matched = True
                            break
                    if not content_matched:
                        continue

                filtered_files.append(file_name)

        return filtered_files


async def main():
    localizer = FileLocalizer()
    localizer.development_requirement = "division by zero"
    results = await localizer.execute(
        root_directory="/Users/manna/PycharmProjects/Agent-Next-Web/calculator",
        recursive=True,
        file_patterns=["*.py"],
        exclude_patterns=["test_*.py", "*_test.py"],
        regex_pattern=[
            r"divide|division",
            r"def\s+calculate",
        ],
        max_files=3,  # Added parameter
        max_snippets_per_file=2,  # Added parameter
    )


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
