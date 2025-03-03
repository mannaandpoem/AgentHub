import os
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, Any

from pydantic import Field

from app.tool import BaseTool
from app.tool.base import ToolResult
from llm_code_block_localizer import LLMCodeBlockLocalizer
from llm_file_localizer import LLMFileLocalizer
from llm_replace_editor import LLMReplaceEditor


class CodeChangeOrchestrator(BaseTool):
    """
    Tool to orchestrate the entire development process using multiple specialized tools.
    """
    name: str = "code_change_orchestrator"
    description: str = "Orchestrates the entire development process using specialized tools for file localization, code block identification, and code replacement."
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
                "description": "List of file patterns to include (e.g., '*.py')"
            },
            "exclude_patterns": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of file patterns to exclude (e.g., 'test_*.py')"
            },
            "generate_patch": {
                "type": "boolean",
                "description": "Whether to generate a git diff patch for the changes"
            },
            "apply_changes": {
                "type": "boolean",
                "description": "Whether to apply the changes to the files"
            }
        },
        "required": ["request", "repo_path"]
    }

    file_localizer: LLMFileLocalizer = Field(default_factory=LLMFileLocalizer)
    code_block_localizer: LLMCodeBlockLocalizer = Field(default_factory=LLMCodeBlockLocalizer)
    replace_editor: LLMReplaceEditor = Field(default_factory=LLMReplaceEditor)

    async def execute(self, **kwargs) -> ToolResult:
        """
        Execute the complete development process.
        Returns:
            A ToolResult containing a detailed report of the development process
        """
        request = kwargs.get("request")
        repo_path = kwargs.get("repo_path")
        file_patterns = kwargs.get("file_patterns", ["*.py"])
        exclude_patterns = kwargs.get("exclude_patterns", [])
        generate_patch = kwargs.get("generate_patch", True)
        apply_changes = kwargs.get("apply_changes", True)

        if not request:
            return ToolResult(error="Development request is required")

        if not repo_path:
            return ToolResult(error="Repository path is required")

        repo = Path(repo_path)
        if not repo.exists():
            return ToolResult(error=f"Repository path '{repo_path}' does not exist")

        # Initialize report
        report = [f"Development Request: {request}", "=" * 80, ""]
        patches = []

        # Step 1: Locate the most relevant files
        report.append("STEP 1: Locating the most relevant files...")
        try:
            locate_result = await self.file_localizer.execute(
                request=request,
                repo_path=repo_path,
                file_patterns=file_patterns,
                exclude_patterns=exclude_patterns,
                top_n=3
            )

            if locate_result.error:
                report.append(f"Error: {locate_result.error}")
                return ToolResult(output="\n".join(report))

            report.append(locate_result.output)

            # Check if we have located files or need to create a new one
            if locate_result.system and "suggested_file:" in locate_result.system:
                # Need to create a new file
                suggested_file = locate_result.system.split("suggested_file:")[1].strip()
                report.append(f"\nNo relevant files found. Will create new file: {suggested_file}")

                # Step 2: Create the new file
                report.append("\nSTEP 2: Creating new file...")
                create_result = await self.replace_editor.execute(
                    request=request,
                    file_path=suggested_file,
                    repo_path=repo_path,
                    is_new_file=True,
                    generate_patch=generate_patch,
                    apply_changes=apply_changes
                )

                if create_result.error:
                    report.append(f"Error: {create_result.error}")
                    return ToolResult(output="\n".join(report))

                report.append(create_result.output)

                # Collect patch if generated
                if create_result.system and "patch:" in create_result.system:
                    patch = create_result.system.split("patch:")[1]
                    if patch.strip():
                        patches.append(patch)
                        report.append("\nGenerated patch for file creation")

                report.append("\nDevelopment process completed successfully!")

                # Return final report and patches
                return ToolResult(
                    output="\n".join(report),
                    system=f"patches:{len(patches)}" if patches else ""
                )

            elif locate_result.system and "located_files:" in locate_result.system:
                # Process located files
                located_files = locate_result.system.split("located_files:")[1].split(",")

                report.append(f"\nProcessing {len(located_files)} files...")

                # For each located file, find code blocks and generate replacements
                for file_idx, file_path in enumerate(located_files, 1):
                    # Clean up file path
                    file_path = file_path.strip()

                    report.append(f"\nFile {file_idx}: {file_path}")
                    report.append("-" * 60)

                    # Step 2: Locate relevant code blocks
                    report.append(f"STEP 2.{file_idx}: Locating relevant code blocks...")

                    block_result = await self.code_block_localizer.execute(
                        request=request,
                        file_path=file_path,
                        repo_path=repo_path,
                        max_blocks=3
                    )

                    if block_result.error:
                        report.append(f"Error: {block_result.error}")
                        report.append("Skipping this file and continuing with others...")
                        continue

                    report.append(block_result.output)

                    # Check if we found code blocks
                    if "no_code_blocks_found" in (block_result.system or ""):
                        report.append("No relevant code blocks found. Will add new functionality.")

                        # Add new functionality to the file
                        add_result = await self.replace_editor.execute(
                            request=request,
                            file_path=file_path,
                            repo_path=repo_path,
                            code_blocks=[],  # Empty list to indicate adding new functionality
                            generate_patch=generate_patch,
                            apply_changes=apply_changes
                        )

                        if add_result.error:
                            report.append(f"Error: {add_result.error}")
                            continue

                        report.append(add_result.output)

                        # Collect patch if generated
                        if add_result.system and "patch:" in add_result.system:
                            patch = add_result.system.split("patch:")[1]
                            if patch.strip():
                                patches.append(patch)
                                report.append("Generated patch for new functionality")

                    elif block_result.system and "code_blocks:" in block_result.system:
                        # Step 3: Generate and apply replacements
                        report.append(f"STEP 3.{file_idx}: Generating and applying replacements...")

                        code_blocks = block_result.system.split("code_blocks:")[1]

                        replace_result = await self.replace_editor.execute(
                            request=request,
                            file_path=file_path,
                            repo_path=repo_path,
                            code_blocks=code_blocks,
                            generate_patch=generate_patch,
                            apply_changes=apply_changes
                        )

                        if replace_result.error:
                            report.append(f"Error: {replace_result.error}")
                            continue

                        report.append(replace_result.output)

                        # Collect patch if generated
                        if replace_result.system and "patch:" in replace_result.system:
                            patch = replace_result.system.split("patch:")[1]
                            if patch.strip():
                                patches.append(patch)
                                report.append("Generated patch for replacements")
            else:
                report.append("\nNo files were located. Development process cannot continue.")
                return ToolResult(output="\n".join(report))

        except Exception as e:
            report.append(f"Error in development process: {str(e)}")
            return ToolResult(
                output="\n".join(report),
                error=str(e)
            )

        # Create a combined patch file if requested
        if generate_patch and patches:
            combined_patch = "\n".join(patches)
            try:
                patch_path = Path(repo_path) / "changes.patch"
                with open(patch_path, "w") as f:
                    f.write(combined_patch)
                report.append(f"\nCombined patch file created: {patch_path}")
            except Exception as e:
                report.append(f"\nError creating combined patch file: {str(e)}")

        report.append("\nDevelopment process completed successfully!")

        return ToolResult(
            output="\n".join(report),
            system=f"patches:{len(patches)}" if patches else ""
        )

    async def apply_patch(self, repo_path: str, patch_content: str) -> ToolResult:
        """
        Apply a patch to the repository.

        Args:
            repo_path: Path to the repository
            patch_content: Content of the patch to apply

        Returns:
            ToolResult indicating success or failure
        """
        if not patch_content.strip():
            return ToolResult(error="Patch is empty")

        # Create a temporary patch file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.patch', delete=False) as temp_file:
            temp_file_path = temp_file.name
            temp_file.write(patch_content)

        original_dir = os.getcwd()
        try:
            # Try to apply the patch
            os.chdir(repo_path)

            # Check if patch can be applied
            check_result = subprocess.run(
                ["git", "apply", "--check", temp_file_path],
                capture_output=True,
                text=True
            )

            if check_result.returncode != 0:
                # If check fails, try with --ignore-whitespace
                check_result = subprocess.run(
                    ["git", "apply", "--check", "--ignore-whitespace", temp_file_path],
                    capture_output=True,
                    text=True
                )

                if check_result.returncode != 0:
                    return ToolResult(error=f"Patch cannot be applied: {check_result.stderr}")
                else:
                    # Apply with --ignore-whitespace
                    apply_result = subprocess.run(
                        ["git", "apply", "--ignore-whitespace", temp_file_path],
                        capture_output=True,
                        text=True
                    )
            else:
                # Apply the patch normally
                apply_result = subprocess.run(
                    ["git", "apply", temp_file_path],
                    capture_output=True,
                    text=True
                )

            if apply_result.returncode != 0:
                return ToolResult(error=f"Failed to apply patch: {apply_result.stderr}")

            return ToolResult(output="Patch applied successfully")

        except Exception as e:
            return ToolResult(error=f"Error applying patch: {str(e)}")

        finally:
            os.chdir(original_dir)
            # Clean up the temporary file
            os.unlink(temp_file_path)


if __name__ == "__main__":
    # Example usage
    # request = "Add a new function to the calculator.py file to calculate the square of a number."
    # repo_path = "/path/to/your/repository"  # Change to your actual repository path
    request = "Add a new function to the calculator.py file to calculate the square of a number."
    repo_path = "/Users/manna/PycharmProjects/AgentHub/workspace/calculator"  # Change to your actual repository path

    import asyncio

    # Example usage
    orchestrator = CodeChangeOrchestrator()
    result = asyncio.run(orchestrator.execute(request=request, repo_path=repo_path))

    print(result)
