from typing import ClassVar, Optional

from pydantic import BaseModel, Field

from app.tool.tool import Tool


class AttemptCompletionRequest(BaseModel):
    result: str = Field(
        description="(required) The result of the task. Formulate this result in a way that is final "
        "and does not require further input from the user. Don't end your result with "
        "questions or offers for further assistance."
    )
    command: Optional[str] = Field(
        default=None,
        description="(optional) Any command that was executed as part of the completion.",
    )

    def to_string(self) -> str:
        command_text = self.command or "no command provided"
        return f"""<attempt_completion>
<result>
{self.result}
</result>
<command>
{command_text}
</command>
</attempt_completion>"""


class AttemptCompletion(Tool):
    name: ClassVar[str] = "attempt_completion"
    description: ClassVar[
        str
    ] = """
    Use this when you have resolved the Github Issue and solved it completely or you have
    enough evidence to suggest that the Github Issue has been resolved after your changes.
    """
    parameters: ClassVar[dict] = {
        "type": "object",
        "properties": {
            "result": {
                "type": "string",
                "description": "(required) The result of the task. Formulate this result in a way "
                "that is final and does not require further input from the user. Don't "
                "end your result with questions or offers for further assistance.",
            },
            "command": {
                "type": "string",
                "description": "(optional) Any command that was executed as part of the completion.",
            },
        },
        "required": ["result"],
    }

    async def execute(self, result: str, command: Optional[str] = None) -> str:
        """
        Execute the attempt completion with the given result and optional command.

        Args:
            result: The final result of the task
            command: Optional command that was executed

        Returns:
            Formatted string containing the completion attempt details
        """
        request = AttemptCompletionRequest(result=result, command=command)
        return request.to_string()
