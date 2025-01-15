from typing import Any, Dict

from .base import BaseTool, ToolResult


class CodeReviewResult(ToolResult):
    status: str = ""
    comments: str = ""

    def __str__(self):
        return f"Code review status: {self.status}\n{self.comments}".strip()


class CodeReview(BaseTool):
    name: str = "code_review"
    description: str = """Reviews code changes against development requirements and best practices.
    Provides final validation with clear pass/fail feedback."""

    parameters: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "status": {
                "type": "string",
                "description": "Review status - LGTM (Looks Good To Me) for pass, LBTM (Looks Bad To Me) for fail",
                "enum": ["LGTM", "LBTM"],
            },
            "comments": {
                "type": "string",
                "description": "Review comments, must be non-empty if status is LBTM, should be empty if LGTM",
            },
        },
        "required": ["status", "comments"],
    }

    async def execute(self, **kwargs) -> CodeReviewResult:
        """
        Execute the review decision.
        Simply returns the LLM's review decision in a standardized format.
        """
        status = kwargs.get("status")
        comments = kwargs.get("comments", "")

        if status not in ["LGTM", "LBTM"]:
            raise ValueError("Status must be either LGTM or LBTM")

        if status == "LBTM" and not comments.strip():
            raise ValueError("Comments are required when status is LBTM")

        if status == "LGTM" and comments.strip():
            comments = ""  # Clear comments for LGTM status

        return CodeReviewResult(status=status, comments=comments)
