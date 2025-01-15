from app.tool.base import BaseTool


_FINISH_DESCRIPTION = """Finish the interaction when the task is complete OR if the assistant cannot proceed further with the task."""


class Finish(BaseTool):
    name: str = "finish"
    description: str = _FINISH_DESCRIPTION

    async def execute(self):
        """Finish the current execution"""
