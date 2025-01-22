from typing import List, Optional, Literal

from app.tool import Bash
from app.tool.base import BaseTool
from app.tool.oh_editor import OHEditor


class View(BaseTool):
    name: str = "view"
    description: str = """View contents of a file or directory with optional diff view
* If path is a file, displays the contents with line numbers (like `cat -n`)
* If path is a directory, lists non-hidden files and directories up to 2 levels deep
* Optional view_range parameter allows viewing specific line ranges in a file
* Optional view_mode parameter:
  - "normal": Standard view (default)
  - "diff": Shows uncommitted changes in git diff format
  - "full_diff": Shows both staged and unstaged changes
* Line numbers start at 1
* For large files, output may be truncated and marked with <response clipped>
"""
    parameters: dict = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Absolute path to file or directory to view (e.g. '/workspace/file.py' or '/workspace')"
            },
            "view_range": {
                "type": "array",
                "items": {"type": "integer"},
                "description": "Optional line range to view [start_line, end_line]. If not provided, shows entire file. Example: [1, 10] shows first 10 lines"
            },
            "view_mode": {
                "type": "string",
                "enum": ["normal", "diff", "full_diff"],
                "description": "View mode: 'normal' for standard view, 'diff' for uncommitted changes, 'full_diff' for all changes including staged",
                "default": "normal"
            }
        },
        "required": ["path"]
    }

    editor: OHEditor = OHEditor()

    async def execute(
            self,
            path: str,
            view_range: Optional[List[int]] = None,
            view_mode: Literal["normal", "diff", "full_diff"] = "normal"
    ) -> str:
        """
        Execute the view command with optional diff view.

        Args:
            path: Path to file or directory to view
            view_range: Optional line range to view [start_line, end_line]
            view_mode: View mode selection
                - "normal": Standard view (default)
                - "diff": Shows uncommitted changes (unstaged only)
                - "full_diff": Shows both staged and unstaged changes

        Returns:
            String containing the file contents with line numbers, directory listing,
            or diff output depending on the view_mode
        """
        if view_mode == "normal":
            # Use standard editor view
            return await self.editor.execute(
                command="view",
                path=path,
                view_range=view_range
            )

        # For diff views, we'll use the shell command tool
        shell_tool = Bash()

        if view_mode == "diff":
            # Show only unstaged changes
            command = f"git diff {path}"
        else:  # full_diff
            # Show both staged and unstaged changes
            command = f"git diff HEAD {path}"

        try:
            result = await shell_tool.execute(command=command)
            if not result.strip():
                return f"No changes detected in {path}"
            return result
        except Exception as e:
            # Fallback to normal view if git commands fail
            # (e.g., if file is not in git repository)
            return (
                    f"Unable to show diff view (error: {str(e)})\n"
                    f"Falling back to normal view:\n\n" +
                    await self.editor.execute(
                        command="view",
                        path=path,
                        view_range=view_range
                    )
            )
