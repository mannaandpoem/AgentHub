from typing import ClassVar

from app.tool.tool import Tool


_FINISH_DESCRIPTION = """Finish the interaction when the task is complete OR if the assistant cannot proceed further with the task."""


class Finish(Tool):
    name: ClassVar[str] = "finish"
    description: ClassVar[str] = _FINISH_DESCRIPTION

    def execute(self) -> str:
        """Finish the current execution"""
        return "The interaction has been successfully completed."
