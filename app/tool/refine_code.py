from typing import Dict, Any

from app.tool.base import BaseTool
from app.tool.oh_editor import OHEditor


class RefineCode(BaseTool):
    name: str = "refine_code"
    description: str = """Advanced code optimization tool that performs precise code refinements.
Performs surgical edits to improve existing implementations:
- Identifies exact code segments for replacement
- Maintains original functionality while optimizing
- Focuses on complexity reduction and memory efficiency"""

    parameters: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Absolute path to target file (e.g. '/workspace/main.py')"
            },
            "old_str": {
                "type": "string",
                "description": "EXACT code segment to replace (include full line(s) with original indentation)"
            },
            "new_str": {
                "type": "string",
                "description": "Optimized replacement code that must:\n1. Reduce complexity\n2. Improve memory usage\n3. Maintain identical API"
            }
        },
        "required": ["path", "old_str", "new_str"]
    }
    editor: OHEditor = OHEditor()

    async def execute(self, **kwargs) -> str:
        path = kwargs.get("path", "")
        old_str = kwargs.get("old_str", "")
        new_str = kwargs.get("new_str", "")

        if not path.strip():
            raise ValueError("Target file path required")
        if not old_str.strip():
            raise ValueError("Original code segment required for replacement")
        if not new_str.strip():
            raise ValueError("Optimized replacement code required")

        # Replace old code with refined implementation
        result = await self.editor.execute(
            command="str_replace",
            path=path,
            old_str=old_str,
            new_str=new_str
        )

        return result
