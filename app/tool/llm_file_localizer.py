import re
from pathlib import Path
from typing import Dict, List, Any, Optional

from pydantic import Field

from app.llm import LLM
from app.tool import BaseTool, ListFiles
from app.tool.base import ToolResult


class LLMFileLocalizer(BaseTool):
    """
    Tool to locate the most relevant files in a repository based on a development request.
    """
    name: str = "llm_file_localizer"
    description: str = "Locates the most relevant files in a repository based on a development request."
    parameters: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "request": {
                "type": "string",
                "description": "The development request describing what needs to be done",
            },
            "repo_path": {
                "type": "string",
                "description": "Path to the repository",
            },
            "file_patterns": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of file patterns to include (e.g., '*.py')",
            },
            "exclude_patterns": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of file patterns to exclude (e.g., 'test_*.py')",
            },
            "top_n": {
                "type": "integer",
                "description": "Number of top files to return (default: 3)",
            },
        },
        "required": ["request", "repo_path"]
    }

    llm: LLM = Field(default_factory=LLM)
    list_files_tool: ListFiles = Field(default_factory=ListFiles)

    async def execute(self, **kwargs) -> ToolResult:
        """
        Execute the file localization process.

        Returns:
            A ToolResult containing information about the located files
        """
        request = kwargs.get("request")
        repo_path = kwargs.get("repo_path")
        file_patterns = kwargs.get("file_patterns", ["*.py"])
        exclude_patterns = kwargs.get("exclude_patterns", [])
        top_n = kwargs.get("top_n", 3)

        if not request:
            return ToolResult(error="Development request is required")

        if not repo_path:
            return ToolResult(error="Repository path is required")

        repo = Path(repo_path)
        if not repo.exists():
            return ToolResult(error=f"Repository path '{repo_path}' does not exist")

        # Step 1: List all relevant files in the repository
        self.list_files_tool.files_limit = float("inf")
        files_result = await self.list_files_tool.execute(directory_path=repo, recursive=True)
        files = [str(f) for f in files_result.files]

        if not files:
            return ToolResult(error=f"No files matching patterns {file_patterns} found in {repo_path}")

        # Step 2: Locate the most relevant file using LLM
        try:
            located_files = await self._locate_files_with_llm(request, repo, files, top_n)

            # Check if we have a file
            if not located_files:
                # Fallback: suggest creating a new file
                suggestion = await self._suggest_new_file(request, repo)
                return ToolResult(
                    output=f"No relevant files found. Suggested new file: {suggestion}",
                    system=f"suggested_file:{suggestion}"
                )

            result_output = "Located files:\n"
            for i, file_info in enumerate(located_files, 1):
                file_path = file_info["file_path"]
                relevance = file_info.get("relevance", "")
                result_output += f"{i}. {file_path}" + (f" - {relevance}" if relevance else "") + "\n"

            return ToolResult(
                output=result_output,
                system=f"located_files:{','.join([f['file_path'] for f in located_files])}"
            )

        except Exception as e:
            return ToolResult(error=f"Error locating files: {str(e)}")

    async def _locate_files_with_llm(
            self, request: str, repo: Path, files: List[str], top_n: int
    ) -> List[Dict[str, Any]]:
        """
        Locate the most relevant files using LLM.

        Args:
            request: The development request
            repo: Path to the repository
            files: List of file paths to consider
            top_n: Number of top files to return

        Returns:
            List of dictionaries with file paths and relevance explanations
        """
        # Limit the number of files to analyze to prevent context overflow
        if len(files) > 100:
            files = files[:100]

        files_list = "\n".join(files)

        prompt = f"""You are a specialized file locator to find the most relevant files in a repository.
Given the development request: 
<github_request>
{request}
</github_request>

Here are the files in the repository:
<repo_structure>
{files_list}
</repo_structure>

Please select {top_n} files that are most likely relevant to implement this request.
For each file, provide an explanation of why it's relevant.

Output the results in this format:
<file_1>path_to_file_1.py</file_1>
<relevance_1>Explanation of why this file is relevant</relevance_1>

<file_2>path_to_file_2.py</file_2>
<relevance_2>Explanation of why this file is relevant</relevance_2>

...and so on.

If no files seem relevant, suggest a new file that should be created with this format:
<new_file>path_to_new_file.py</new_file>
<reason>Explanation of why a new file is needed</reason>
"""

        response = await self.llm.ask([{"role": "user", "content": prompt}])

        # Extract file paths and relevance explanations
        located_files = []

        # Check if we're suggesting a new file
        new_file_match = re.search(r"<new_file>(.*?)</new_file>", response, re.DOTALL)
        if new_file_match:
            new_file = new_file_match.group(1).strip()
            reason_match = re.search(r"<reason>(.*?)</reason>", response, re.DOTALL)
            reason = reason_match.group(1).strip() if reason_match else ""

            return [{
                "file_path": new_file,
                "relevance": reason,
                "is_new": True
            }]

        # Extract existing files
        for i in range(1, top_n + 1):
            file_match = re.search(f"<file_{i}>(.*?)</file_{i}>", response, re.DOTALL)
            if not file_match:
                break

            file_path = file_match.group(1).strip()

            relevance_match = re.search(f"<relevance_{i}>(.*?)</relevance_{i}>", response, re.DOTALL)
            relevance = relevance_match.group(1).strip() if relevance_match else ""

            # Verify the file exists
            if file_path in files or (repo / file_path).exists():
                located_files.append({
                    "file_path": file_path,
                    "relevance": relevance,
                    "is_new": False
                })

        return located_files

    async def _suggest_new_file(self, request: str, repo: Optional[Path] = None) -> str:
        """
        Suggest a new file path based on the development request.

        Args:
            request: The development request
            repo: Path to the repository

        Returns:
            Suggested file path
        """
        prompt = f"""Based on this development request, suggest an appropriate file path/name that should be created:

<request>
{request}
</request>

Format your response exactly like this:
<suggested_file>path/to/suggested_file.py</suggested_file>
"""

        response = await self.llm.ask([{"role": "user", "content": prompt}])

        match = re.search(r"<suggested_file>(.*?)</suggested_file>", response, re.DOTALL)
        if match:
            return match.group(1).strip()

        # Fallback to a generic name if no match
        return "new_implementation.py"
