from app.tool.base import BaseTool

_ATTEMPT_COMPLETION_DESCRIPTION = """Use this tool when you need to mark a software development task as completed. 
The task should meet all requirements, pass necessary tests, and be ready for deployment."""


class AttemptCompletion(BaseTool):
    name: str = "attempt_completion"
    description: str = _ATTEMPT_COMPLETION_DESCRIPTION
    parameters: dict = {
        "type": "object",
        "properties": {
            "result": {
                "type": "string",
                "description": "(required) Provide a clear summary of what was completed and confirm all requirements are met. State the final outcome without questions or open items.",
            }
        },
        "required": ["result"],
    }

    async def execute(self, result: str) -> str:
        """
        Execute the attempt_completion tool.

        Args:
            result: The final result of the task

        Returns:
            str: The result of the attempt completion
        """
        return result
