from app.tool.base import BaseTool


_ATTEMPT_COMPLETION_DESCRIPTION = "Use this when you have resolved the Github Issue and solved it completely or you have enough evidence to suggest that the Github Issue has been resolved after your changes."


class AttemptCompletionClientRequest(BaseTool):
    name: str = "attempt_completion"
    description: str = _ATTEMPT_COMPLETION_DESCRIPTION
    parameters: dict = {
        "type": "object",
        "properties": {
            "result": {
                "type": "string",
                "description": "(required) The result of the task. Formulate this result in a way that is final and does not require further input from the user. Don't end your result with questions or offers for further assistance.",
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
