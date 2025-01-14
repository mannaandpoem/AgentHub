import json
from pathlib import Path
from typing import Any, Dict, List, Union

from pydantic import BaseModel, Field

from app.llm import LLM
from app.tool import (
    BaseTool,
    CreateChatCompletion,
    Filemap,
    ListFiles,
    StrReplaceEditor,
    ToolCollection,
)


class FoundLocations:
    def __init__(self):
        self.locations: Dict[str, List[str]] = {}

    def add_location(self, file_path: str, code_snippets: List[str]):
        self.locations[file_path] = code_snippets

    def to_string(self) -> str:
        result = []
        for file_path, snippets in self.locations.items():
            result.append(f"File: {file_path}\nCode Snippets:\n")
            for snippet in snippets:
                result.append(f"{snippet}\n---\n")
        return "\n".join(result)


class LocationParameters(BaseModel):
    file_parameters: dict = {
        "type": "object",
        "properties": {
            "file_list": {
                "type": "array",
                "description": "(required) The list of files to localize the issue in.",
            },
        },
        "required": ["file_list"],
    }

    code_snippet_parameters: dict = {
        "type": "object",
        "properties": {
            "code_snippets": {
                "type": "array",
                "description": "(required) The list of fine grain code snippets to localize the issue in the file.",
            },
        },
        "required": ["code_snippets"],
    }


class LLMFileLocalizer(BaseTool):
    name: str = "llm_file_localizer"
    description: str = """
    A tool for localizing code issues by combining file listing, content mapping, and LLM analysis.
    Returns specific file paths and their suspicious code snippets.
    """
    parameters: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "root_directory": {
                "type": "string",
                "description": "The absolute path of the root directory to start the search from.",
            },
            "issue_description": {
                "type": "string",
                "description": "Description of the issue to locate in the codebase.",
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
        "required": ["root_directory", "issue_description"],
    }

    list_files_tool: ListFiles = Field(default_factory=ListFiles)
    filemap_tool: Filemap = Field(default_factory=Filemap)
    editor_tool: StrReplaceEditor = Field(default_factory=StrReplaceEditor)
    tool_collection: ToolCollection = ToolCollection(CreateChatCompletion())
    llm: LLM = Field(default_factory=LLM)

    location_parameters: LocationParameters = LocationParameters()
    found_locations: FoundLocations = FoundLocations()

    async def execute(self, **kwargs) -> Any:
        """
        Execute the localization process and return found locations with code snippets.
        """
        root_dir = kwargs["root_directory"]
        issue_description = kwargs["issue_description"]
        recursive = kwargs["recursive"]
        file_patterns = kwargs.get("file_patterns", ["*.py"])
        exclude_patterns = kwargs.get("exclude_patterns", [])

        # Step 1: List all relevant files using ListFiles tool
        files_result = await self.list_files_tool.execute(
            directory_path=root_dir, recursive=recursive
        )

        found_files = self._filter_files(
            files_result.files, file_patterns, exclude_patterns
        )

        # Step 2: First LLM call to identify suspicious files
        suspicious_files = await self._identify_suspicious_files(
            found_files, issue_description
        )

        # Step 3: Second LLM call to locate specific code snippets
        await self._locate_code_snippets(suspicious_files, issue_description)

        return self.found_locations.to_string()

    async def execute_tool(self, suspicious_files_prompt):
        response = await self.llm.ask_tool(
            messages=[{"role": "user", "content": suspicious_files_prompt}],
            tools=self.tool_collection.to_params(),
            tool_choice="required",
        )
        tool = response.tool_calls[0]
        cmd_name = tool.function.name
        if cmd_name not in self.tool_collection.tool_map:
            raise ValueError(f"Command '{cmd_name}' not found")
        args = json.loads(tool.function.arguments)
        result = await self.tool_collection.execute(name=cmd_name, tool_input=args)
        return result

    async def _identify_suspicious_files(
        self, files: List[str], issue_description: str
    ) -> Any | List[str]:
        """First LLM call to identify suspicious files."""
        suspicious_files_prompt = (
            f"Given the following issue description: {issue_description}\n"
        )

        all_file_content = []
        for file_path in files:
            # Get file content using Filemap
            file_content = await self.filemap_tool.execute(file_path=file_path)
            all_file_content.append(f"---{file_path}\n{file_content}\n")

        suspicious_files_prompt += (
            "\n".join(all_file_content)
            + "\nPlease select the files that may contain the issue."
        )

        create_chat_completion_tool = self.tool_collection.get_tool(
            "create_chat_completion"
        )
        create_chat_completion_tool.parameters = (
            self.location_parameters.file_parameters
        )
        create_chat_completion_tool.response_type = List[str]
        create_chat_completion_tool.required = ["file_list"]

        result = await self.execute_tool(suspicious_files_prompt)
        return result

    async def _locate_code_snippets(
        self, suspicious_files: List[str], issue_description: str
    ):
        """Second LLM call to locate specific code snippets."""
        create_chat_completion_tool = self.tool_collection.get_tool(
            "create_chat_completion"
        )
        create_chat_completion_tool.parameters = (
            self.location_parameters.code_snippet_parameters
        )
        create_chat_completion_tool.response_type = List[str]
        create_chat_completion_tool.required = ["code_snippets"]
        for file_path in suspicious_files:
            # Read the file content
            file_content = await self.editor_tool.execute(
                path=file_path, command="view"
            )
            # Prepare prompt for code snippet identification
            snippet_prompt = (
                f"Given this issue description: {issue_description}\n{file_content}"
            )

            # Execute LLM tool to locate code snippets
            result = await self.execute_tool(snippet_prompt)

            self.found_locations.add_location(file_path, result)

    @staticmethod
    def _filter_files(
        files: List[Union[str, Path]],
        include_patterns: List[str],
        exclude_patterns: List[str],
    ) -> List[str]:
        """Filter files based on include and exclude patterns."""
        import fnmatch

        filtered_files = []
        for file_path in files:
            file_name = (
                file_path.strip() if isinstance(file_path, str) else str(file_path)
            )
            if not file_name:
                continue

            # Check include patterns
            included = any(
                fnmatch.fnmatch(file_name, pattern) for pattern in include_patterns
            )

            # Check exclude patterns
            excluded = any(
                fnmatch.fnmatch(file_name, pattern) for pattern in exclude_patterns
            )

            if included and not excluded:
                filtered_files.append(file_name)

        return filtered_files


async def main():
    localizer = LLMFileLocalizer()
    results = await localizer.execute(
        root_directory="/Users/manna/PycharmProjects/Agent-Next-Web/calculator",
        issue_description="division by zero",
        recursive=True,
        file_patterns=["*.py"],
        exclude_patterns=["test_*.py", "*_test.py"],
    )

    print(results)


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
