from pathlib import Path
import re
import os
import tempfile
import subprocess
import shutil
from typing import Dict, List, Any, Optional

from pydantic import BaseModel, Field

from app.llm import LLM
from app.tool import BaseTool
from app.tool.base import ToolResult


class CodeReplacement(BaseModel):
    """Represents a code replacement to be applied."""
    original: str
    replacement: str
    start_line: int
    end_line: int
    explanation: str = ""


class LLMReplaceEditor(BaseTool):
    """
    Tool to generate and apply replacements for identified code blocks based on development requests.
    """
    name: str = "llm_replace_editor"
    description: str = "Generates replacements for identified code blocks based on development requests."
    parameters: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "request": {
                "type": "string",
                "description": "The development request describing what needs to be done",
            },
            "file_path": {
                "type": "string",
                "description": "Path to the file to edit",
            },
            "repo_path": {
                "type": "string",
                "description": "Path to the repository containing the file",
            },
            "code_blocks": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "code": {"type": "string"},
                        "start_line": {"type": "integer"},
                        "end_line": {"type": "integer"},
                        "explanation": {"type": "string"}
                    }
                },
                "description": "List of code blocks to replace"
            },
            "generate_patch": {
                "type": "boolean",
                "description": "Whether to generate a git diff patch for the changes"
            },
            "apply_changes": {
                "type": "boolean",
                "description": "Whether to apply the changes to the file"
            },
            "is_new_file": {
                "type": "boolean",
                "description": "Whether this is a new file to be created"
            }
        },
        "required": ["request", "file_path"]
    }

    llm: LLM = Field(default_factory=LLM)

    async def execute(self, **kwargs) -> ToolResult:
        """
        Execute the code replacement process.

        Returns:
            A ToolResult containing information about the replacements made
        """
        request = kwargs.get("request")
        file_path = kwargs.get("file_path")
        repo_path = kwargs.get("repo_path", "")
        code_blocks = kwargs.get("code_blocks", [])
        generate_patch = kwargs.get("generate_patch", True)
        apply_changes = kwargs.get("apply_changes", True)
        is_new_file = kwargs.get("is_new_file", False)

        if not request:
            return ToolResult(error="Development request is required")

        if not file_path:
            return ToolResult(error="File path is required")

        # Convert code_blocks to expected format if needed
        if isinstance(code_blocks, str):
            try:
                # Try to parse from a system output format
                parsed_blocks = []
                for block_str in code_blocks.split(';'):
                    parts = block_str.split(':', 2)
                    if len(parts) >= 3:
                        start_line, end_line, code = parts
                        # Replace any encoded colons
                        code = code.replace('&#58;', ':')
                        parsed_blocks.append({
                            "code": code,
                            "start_line": int(start_line),
                            "end_line": int(end_line),
                            "explanation": ""
                        })
                code_blocks = parsed_blocks
            except:
                # If parsing fails, assume an empty list
                code_blocks = []

        # Determine full file path
        if repo_path:
            full_path = Path(repo_path) / file_path
        else:
            full_path = Path(file_path)

        original_content = ""
        if full_path.exists() and not is_new_file:
            # Read existing file content
            try:
                original_content = full_path.read_text()
            except Exception as e:
                return ToolResult(error=f"Error reading file: {str(e)}")
        else:
            # This is a new file
            is_new_file = True

        try:
            result_output = ""
            if is_new_file:
                # Generate content for a new file
                new_content = await self._create_new_file_with_llm(request, file_path, repo_path)
            else:
                # Generate replacements for existing file
                result = await self._replace_edit_file_with_llm(
                    request, file_path, original_content, code_blocks
                )

                if not result["success"]:
                    return ToolResult(error=f"Error generating replacements: {result.get('error', 'Unknown error')}")

                new_content = result["content"]
                replacements = result["replacements"]

                # Format the output
                result_output = f"Generated {len(replacements)} replacements for '{file_path}':\n"
                for i, rep in enumerate(replacements, 1):
                    result_output += f"\nReplacement {i} (lines {rep['start_line']}-{rep['end_line']}):\n"
                    result_output += "-" * 50 + "\n"
                    result_output += "Original code:\n"
                    result_output += rep["original"] + "\n\n"
                    result_output += "Replacement code:\n"
                    result_output += rep["replacement"] + "\n"
                    result_output += "-" * 50 + "\n"
                    result_output += f"Explanation: {rep['explanation']}\n"

            # Generate patch if requested
            patch = ""
            if generate_patch:
                patch = await self._generate_patch(
                    file_path, original_content, new_content, Path(repo_path) if repo_path else None, is_new_file
                )

            # Apply changes if requested
            if apply_changes:
                success = await self._apply_replacements_to_file(str(full_path), new_content)
                if not success:
                    return ToolResult(
                        output=result_output if not is_new_file else f"Generated content for new file '{file_path}'",
                        error=f"Failed to write changes to '{file_path}'",
                        system=f"patch:{patch}" if patch else ""
                    )

            # Return result
            output = f"{'Created new file' if is_new_file else 'Updated file'}: {file_path}"
            if not is_new_file and 'result_output' in locals():
                output = result_output

            return ToolResult(
                output=output,
                system=f"patch:{patch}" if patch else ""
            )

        except Exception as e:
            return ToolResult(error=f"Error replacing code: {str(e)}")

    async def _replace_edit_file_with_llm(
            self, request: str, file_path: str, file_content: str, code_blocks: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Generate replacements for identified code blocks.

        Args:
            request: The development request
            file_path: Path to the file
            file_content: Current content of the file
            code_blocks: List of code blocks to replace

        Returns:
            Dictionary with success status, content, and replacements
        """
        if not code_blocks:
            return {
                "success": False,
                "error": "No code blocks provided for replacement",
                "replacements": [],
            }

        prompt = f"""You are a specialized code editor. You need to modify specific code blocks to fulfill a development request.

Given the development request:
<github_request>
{request}
</github_request>

Here is the content of the file {file_path}:
<file_content>
{file_content}
</file_content>

You need to replace the following code blocks with improved versions that fulfill the request:

"""

        # Add each code block to the prompt
        for i, block in enumerate(code_blocks, 1):
            code = block.get("code", "")
            start_line = block.get("start_line", 0)
            end_line = block.get("end_line", 0)
            explanation = block.get("explanation", "")

            prompt += f"""
<original_block_{i}>
{code}
</original_block_{i}>
<start_line_{i}>{start_line}</start_line_{i}>
<end_line_{i}>{end_line}</end_line_{i}>
<explanation_{i}>{explanation}</explanation_{i}>

"""

        prompt += """
For each original block, provide a replacement that implements the requested changes:

<replacement_block_1>
# Improved code that fulfills the request
</replacement_block_1>
<explanation_1>Explain what changes you made and why</explanation_1>

Continue with additional blocks if there are multiple blocks to replace:

<replacement_block_2>
# Improved code for the second block
</replacement_block_2>
<explanation_2>Explanation for second replacement</explanation_2>

<replacement_block_3>
# Improved code for the third block
</replacement_block_3>
<explanation_3>Explanation for third replacement</explanation_3>

IMPORTANT:
1. Ensure the replacement code maintains the EXACT SAME INDENTATION as the original code block.
2. Make sure the replacements maintain the overall functionality while addressing the request.
3. The replacement must be complete blocks - do NOT use ellipses or "..." in your code.
4. Only provide the <replacement_block_N> and <explanation_N> tags in your response.
"""

        # Generate replacements using LLM
        try:
            response = await self.llm.ask(messages=[{"role": "user", "content": prompt}])

            # Extract replacements
            replacements = []

            # Process file content as a list of lines for easier replacement
            content_lines = file_content.splitlines()

            # Sort code blocks by start line in descending order to avoid index issues during replacement
            sorted_blocks = sorted(code_blocks, key=lambda x: x["start_line"], reverse=True)

            for i, block in enumerate(sorted_blocks):
                block_num = sorted_blocks.index(block) + 1
                replacement_match = re.search(
                    f"<replacement_block_{block_num}>(.*?)</replacement_block_{block_num}>",
                    response,
                    re.DOTALL,
                )
                explanation_match = re.search(
                    f"<explanation_{block_num}>(.*?)</explanation_{block_num}>", response, re.DOTALL
                )

                if replacement_match:
                    new_code = replacement_match.group(1).strip()
                    explanation = (
                        explanation_match.group(1).strip() if explanation_match else ""
                    )

                    # Record the replacement
                    replacements.append(
                        {
                            "original": block["code"],
                            "replacement": new_code,
                            "start_line": block["start_line"],
                            "end_line": block["end_line"],
                            "explanation": explanation,
                        }
                    )

                    # Calculate number of lines in original block and replacement
                    orig_lines_count = len(block["code"].splitlines())
                    new_lines_count = len(new_code.splitlines())

                    # Replace the old code with the new code
                    content_lines[block["start_line"] - 1: block["end_line"]] = new_code.splitlines()

                    # Adjust subsequent block line numbers if the replacement changed the line count
                    line_diff = new_lines_count - orig_lines_count
                    if line_diff != 0:
                        for j, other_block in enumerate(sorted_blocks):
                            if j > i and other_block["start_line"] > block["start_line"]:
                                sorted_blocks[j]["start_line"] += line_diff
                                sorted_blocks[j]["end_line"] += line_diff

            # Combine lines back into a single string
            new_content = "\n".join(content_lines)

            return {
                "success": True,
                "content": new_content,
                "replacements": replacements,
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "replacements": [],
            }

    async def _create_new_file_with_llm(self, request: str, file_path: str, repo_path: Optional[str] = None) -> str:
        """
        Create a new file with content based on the development request.

        Args:
            request: The development request
            file_path: Path to create the file
            repo_path: Path to the repository (optional)

        Returns:
            The content created for the new file
        """
        # Find similar files for context if repo_path is provided
        similar_file_contents = []
        if repo_path:
            repo = Path(repo_path)

            # Get file extension to look for similar files
            file_ext = Path(file_path).suffix
            name_part = Path(file_path).stem

            # Look for similar files
            similar_files = []

            # Method 1: Files with similar names
            for f in repo.glob(f"**/*{name_part}*{file_ext}"):
                similar_files.append(str(f.relative_to(repo)))

            # Method 2: Files with the same extension in the same directory
            file_dir = str(Path(file_path).parent)
            if file_dir:
                dir_path = repo / file_dir
                if dir_path.exists():
                    for f in dir_path.glob(f"*{file_ext}"):
                        similar_files.append(str(f.relative_to(repo)))

            # Limit to top 3 most relevant files
            similar_files = sorted(list(set(similar_files)))[:3]

            # Read similar files for context
            for sf in similar_files:
                try:
                    content = (repo / sf).read_text()
                    similar_file_contents.append(f"File: {sf}\n\n{content}")
                except Exception as e:
                    # Skip files that can't be read
                    pass

        similar_context = "\n\n---\n\n".join(similar_file_contents)

        prompt = f"""You need to create a new file based on a development request.

Development Request:
<github_request>
{request}
</github_request>

File to create:
<filepath>{file_path}</filepath>

{'Here are similar files for reference:' if similar_file_contents else ''}
{'<similar_files>' + similar_context + '</similar_files>' if similar_file_contents else ''}

Please create appropriate content for this file that would fulfill the development request.
Return only the file content, properly formatted and complete with all necessary imports, classes, and functions.
"""

        # Generate file content using LLM
        file_content = await self.llm.ask(messages=[{"role": "user", "content": prompt}])

        # Clean up the content if the LLM wrapped it in code blocks
        file_content = re.sub(r'^```python\n', '', file_content)
        file_content = re.sub(r'\n```$', '', file_content)
        file_content = re.sub(r'^```\n', '', file_content)
        file_content = re.sub(r'\n```$', '', file_content)

        return file_content

    async def _apply_replacements_to_file(self, file_path: str, content: str) -> bool:
        """
        Write content to the specified file.

        Args:
            file_path: Path to the file
            content: Content to write

        Returns:
            Boolean indicating success
        """
        try:
            path = Path(file_path)
            # Create directories if they don't exist
            path.parent.mkdir(parents=True, exist_ok=True)
            # Normalize line endings for the OS
            normalized_content = content.replace('\r\n', '\n')
            path.write_text(normalized_content)
            return True
        except Exception as e:
            print(f"Error writing to file: {str(e)}")
            return False

    async def _generate_patch(
            self,
            file_path: str,
            original_content: str,
            new_content: str,
            repo_path: Optional[Path] = None,
            file_creation: bool = False
    ) -> str:
        """
        Generate a git diff patch for changes.

        Args:
            file_path: Path to the file (relative to repo)
            original_content: Original content
            new_content: New content
            repo_path: Path to repository (optional)
            file_creation: Whether this is a new file

        Returns:
            String containing the git diff patch
        """
        if repo_path is None:
            repo_path = Path.cwd()

        original_dir = os.getcwd()
        temp_dir = None

        try:
            # Create temporary directory and initialize git repo
            temp_dir = Path(tempfile.mkdtemp())
            os.chdir(temp_dir)
            subprocess.run(["git", "init", "-q"], check=True)

            # Create necessary directories for the file
            rel_file_path = Path(file_path)
            abs_file_path = temp_dir / rel_file_path
            abs_file_path.parent.mkdir(parents=True, exist_ok=True)

            # Configure git user
            subprocess.run(["git", "config", "user.email", "patch@example.com"], check=True)
            subprocess.run(["git", "config", "user.name", "Patch Generator"], check=True)

            # Handle file creation vs modification
            if file_creation:
                # Create empty file first (for git to track its creation)
                abs_file_path.touch()
                subprocess.run(["git", "add", str(rel_file_path)], check=True)
                subprocess.run(["git", "commit", "-m", "Initial commit"], check=True)

                # Now create the actual file with new content
                abs_file_path.write_text(new_content)
                subprocess.run(["git", "add", str(rel_file_path)], check=True)
            else:
                # Write original content, commit, then update
                abs_file_path.write_text(original_content)
                subprocess.run(["git", "add", str(rel_file_path)], check=True)
                subprocess.run(["git", "commit", "-m", "Original"], check=True)

                # Write new content
                abs_file_path.write_text(new_content)
                subprocess.run(["git", "add", str(rel_file_path)], check=True)

            # Generate diff
            result = subprocess.run(
                ["git", "diff", "--cached", "--no-color",
                 f"--src-prefix=a/", f"--dst-prefix=b/"],
                capture_output=True,
                text=True,
                check=True
            )

            diff_content = result.stdout

            if not diff_content.strip():
                print("Warning: No changes detected in the diff")

            return diff_content

        except subprocess.CalledProcessError as e:
            print(f"Git command failed: {e.stderr}")
            return ""

        except Exception as e:
            print(f"Error generating patch: {e}")
            return ""

        finally:
            # Clean up
            os.chdir(original_dir)
            if temp_dir:
                shutil.rmtree(temp_dir)
