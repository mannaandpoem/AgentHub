from typing import ClassVar

from app.tool.tool import Tool


_FINISH_DESCRIPTION = """Finish the interaction when the task is complete OR if the assistant cannot proceed further with the task."""


class Finish(Tool):
    name: ClassVar[str] = "finish"
    description: ClassVar[str] = _FINISH_DESCRIPTION
    parameters: ClassVar[dict] = {
        "type": "object",
        "properties": {
            "status": {
                "type": "string",
                "description": "The status of the interaction.",
                "enum": ["success", "failure"],
            }
        },
        "required": ["status"],
    }

    def execute(self, status: str) -> str:
        """Finish the current execution"""
        return f"The interaction has been completed with status: {status}"
