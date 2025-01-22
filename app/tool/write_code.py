from typing import Dict, Any

from app.tool.base import BaseTool
from app.tool.oh_editor import OHEditor

WRITE_CODE_DESCRIPTION = """Creates new source code files with production-ready implementations.

Capabilities:
- Generates complete, executable code files at specified paths
- Follows language-specific best practices and conventions
- Includes comprehensive documentation and type hints
- Implements efficient algorithms (optimized time/space complexity)
- Handles edge cases and errors appropriately

Requirements:
- File path must be absolute and not already exist
- Code must include type annotations, docstrings, and error handling
- Implementation should use optimal data structures and algorithms
"""


class WriteCode(BaseTool):
    name: str = "write_code"
    description: str = WRITE_CODE_DESCRIPTION
    parameters: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": """Absolute file path where the new file will be created.
Example: '/workspace/src/utils.py'
- Must be a valid file path
- Parent directory must exist
- File must not already exist"""
            },
            "file_text": {
                "type": "string",
                "description": """Complete source code implementation including:
1. Proper type hints for all functions/methods
2. Detailed docstrings following language conventions
3. Comprehensive error handling and input validation
4. Efficient algorithmic implementations
5. Clear code organization and structure"""
            }
        },
        "required": ["path", "file_text"]
    }

    editor: OHEditor = OHEditor()

    async def execute(self, **kwargs) -> str:
        path = kwargs.get("path", "")
        file_text = kwargs.get("file_text", "")

        if not path.strip():
            raise ValueError("Absolute file path required")
        if not file_text.strip():
            raise ValueError("Code implementation cannot be empty")

        # Create new file with implemented code
        result = await self.editor.execute(
            command="create",
            path=path,
            file_text=file_text
        )

        return result
