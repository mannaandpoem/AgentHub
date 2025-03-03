import re
from pathlib import Path
from typing import Dict, List, Any

from pydantic import BaseModel, Field

from app.llm import LLM
from app.schema import Message
from app.tool import BaseTool
from app.tool.base import ToolResult


class CodeBlock(BaseModel):
    """Represents a code block identified for modification."""
    code: str
    start_line: int
    end_line: int
    explanation: str = ""


class LLMCodeBlockLocalizer(BaseTool):
    """
    Tool to locate the most relevant code blocks in a file based on a development request.
    """
    name: str = "llm_code_block_localizer"
    description: str = "Locates 1 to 3 most relevant code blocks in a file based on a development request."
    parameters: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "request": {
                "type": "string",
                "description": "The development request describing what needs to be done",
            },
            "file_path": {
                "type": "string",
                "description": "Path to the file to analyze",
            },
            "repo_path": {
                "type": "string",
                "description": "Path to the repository containing the file",
            },
            "max_blocks": {
                "type": "integer",
                "description": "Maximum number of code blocks to identify (default: 3)",
            },
        },
        "required": ["request", "file_path"]
    }
    llm: LLM = Field(default_factory=LLM)

    async def execute(self, **kwargs) -> ToolResult:
        """
        Execute the code block localization process.
        Returns:
            A ToolResult containing information about the located code blocks
        """
        request = kwargs.get("request")
        file_path = kwargs.get("file_path")
        repo_path = kwargs.get("repo_path", "")
        max_blocks = kwargs.get("max_blocks", 3)

        if not request:
            return ToolResult(error="Development request is required")

        if not file_path:
            return ToolResult(error="File path is required")

        # Determine full file path
        if repo_path:
            full_path = Path(repo_path) / file_path
        else:
            full_path = Path(file_path)

        # Check if file exists
        if not full_path.exists():
            return ToolResult(error=f"File '{file_path}' does not exist")

        try:
            # Read file content
            file_content = full_path.read_text()

            # Call the LLM to locate code blocks
            code_blocks = await self._locate_code_blocks_with_llm(
                request, file_content, file_path, max_blocks
            )

            if not code_blocks:
                return ToolResult(
                    output=f"No relevant code blocks found in '{file_path}'.",
                    system="no_code_blocks_found"
                )

            # Format the output
            result_output = f"Located {len(code_blocks)} code blocks in '{file_path}':\n"
            for i, block in enumerate(code_blocks, 1):
                result_output += f"\nBlock {i} (lines {block.start_line}-{block.end_line}):\n"
                result_output += "-" * 50 + "\n"
                result_output += block.code + "\n"
                result_output += "-" * 50 + "\n"
                result_output += f"Explanation: {block.explanation}\n"

            # Prepare a system output that can be parsed by other tools
            system_output = []
            for block in code_blocks:
                system_output.append(
                    f"{block.start_line}:{block.end_line}:{block.code.replace(':', '&#58;')}"
                )

            return ToolResult(
                output=result_output,
                system=f"code_blocks:{';'.join(system_output)}"
            )

        except Exception as e:
            return ToolResult(error=f"Error locating code blocks: {str(e)}")

    async def _locate_code_blocks_with_llm(
            self, request: str, file_content: str, file_path: str, max_blocks: int = 3
    ) -> List[CodeBlock]:
        """
        Locate code blocks using LLM.

        Args:
            request: The development request
            file_content: The content of the file
            file_path: The path to the file
            max_blocks: Maximum number of code blocks to identify

        Returns:
            List of CodeBlock objects
        """
        # Split file into lines for accurate line counting
        file_lines = file_content.splitlines()

        prompt = f"""You are a specialized code analyzer to find 1 to {max_blocks} relevant code blocks in a file.
Given the development request: 
<github_request>
{request}
</github_request>

Here is the content of the file {file_path}:
<file_content>
{file_content}
</file_content>

Please identify 1 to {max_blocks} most relevant code blocks (functions, classes, or sections) that should be modified to fulfill the request.
For each code block, provide the following information:

<code_block_1>
# Exact code block from the file
</code_block_1>
<start_line_1>line_number</start_line_1>
<end_line_1>line_number</end_line_1>
<explanation_1>Explain why this code block is relevant to the request</explanation_1>

If there are additional relevant code blocks, continue with:

<code_block_2>
# Second code block
</code_block_2>
<start_line_2>line_number</start_line_2>
<end_line_2>line_number</end_line_2>
<explanation_2>Explanation for second block</explanation_2>

<code_block_3>
# Third code block
</code_block_3>
<start_line_3>line_number</start_line_3>
<end_line_3>line_number</end_line_3>
<explanation_3>Explanation for third block</explanation_3>

Note: Only include blocks that are truly relevant. It's acceptable to return just 1 or 2 blocks if that's all that's needed.

IMPORTANT: Make sure the line numbers are accurate. The first line of the file is line 1.
Ensure that the code block you identify exactly matches the content between start_line and end_line.
"""

        response = await self.llm.ask([Message.user_message(prompt)])

        # Extract information for up to max_blocks code blocks
        result = []

        for i in range(1, max_blocks + 1):
            # Extract the identified code block
            code_match = re.search(
                f"<code_block_{i}>(.*?)</code_block_{i}>", response, re.DOTALL
            )
            if not code_match:
                break

            code_block = code_match.group(1).strip()

            # Extract line numbers and explanation
            start_match = re.search(f"<start_line_{i}>(.*?)</start_line_{i}>", response)
            end_match = re.search(f"<end_line_{i}>(.*?)</end_line_{i}>", response)
            explanation_match = re.search(
                f"<explanation_{i}>(.*?)</explanation_{i}>", response, re.DOTALL
            )

            if start_match and end_match:
                try:
                    start_line = int(start_match.group(1))
                    end_line = int(end_match.group(1))
                    explanation = (
                        explanation_match.group(1).strip() if explanation_match else ""
                    )

                    # Validate line numbers
                    if start_line < 1:
                        start_line = 1
                    if end_line > len(file_lines):
                        end_line = len(file_lines)
                    if start_line > end_line:
                        start_line, end_line = end_line, start_line

                    # Extract exact code from file using line numbers to ensure they match
                    exact_code = "\n".join(file_lines[start_line - 1:end_line])

                    result.append(CodeBlock(
                        code=exact_code,
                        start_line=start_line,
                        end_line=end_line,
                        explanation=explanation
                    ))
                except ValueError:
                    # Skip if line numbers aren't valid integers
                    continue

        return result

    @staticmethod
    async def check_file_exists_or_create(file_path: str) -> ToolResult:
        """
        Checks if a file exists or suggests creating it.

        Args:
            file_path: Path to the file to check

        Returns:
            ToolResult indicating whether the file exists or should be created
        """
        path = Path(file_path)

        if path.exists():
            return ToolResult(
                output=f"File '{file_path}' exists.",
                system="file_exists:true"
            )

        # File doesn't exist, return suggestion to create it
        return ToolResult(
            output=f"File '{file_path}' doesn't exist. You may want to create it.",
            system="file_exists:false"
        )
