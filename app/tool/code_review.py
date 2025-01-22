from typing import Any, Dict

from .base import BaseTool, ToolResult


class CodeReviewResult(ToolResult):
    status: str = ""
    comments: str = ""

    def __str__(self):
        if self.status == "LGTM":
            return "Code Review Status: APPROVED (LGTM)"
        return f"Code Review Status: REJECTED (LBTM)\n\nIssues Found:\n{self.comments}".strip()


class CodeReview(BaseTool):
    name: str = "code_review"
    description: str = """Comprehensive code review against engineering excellence standards. 
    Provides clear pass/fail decision with detailed technical feedback.

    Code Review Guidelines:
    1. Correctness & Functionality:
       - Verify logical correctness and edge case handling
       - Check for bugs, race conditions, and resource leaks
       - Validate input/output behavior matches specifications

    2. Readability & Maintainability:
       - Enforce coding standards and style consistency
       - Assess naming clarity and code organization
       - Verify proper use of language idioms and patterns

    3. Security & Performance:
       - Identify security vulnerabilities (e.g., injections, XSS)
       - Validate proper error handling and resource cleanup
       - Optimize algorithms and data structure choices

    4. Testing & Documentation:
       - Ensure adequate test coverage and validation
       - Verify documentation matches implementation
       - Check for proper logging and monitoring

    5. Architectural Compliance:
       - Maintain consistency with system architecture
       - Follow separation of concerns principles
       - Adhere to organizational technical strategy

    LGTM requires full compliance; LBTM for any critical issues."""

    parameters: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "status": {
                "type": "string",
                "description": "Final review verdict - LGTM (Looks Good To Me) or LBTM (Looks Bad To Me)",
                "enum": ["LGTM", "LBTM"],
            },
            "comments": {
                "type": "string",
                "description": "Specific technical feedback listing guideline violations (required for LBTM). "
                               "Must be empty for LGTM. Format as bullet points.",
            },
        },
        "required": ["status", "comments"],
    }

    async def execute(self, **kwargs) -> CodeReviewResult:
        """Execute the review decision with quality enforcement"""
        status = kwargs.get("status")
        comments = kwargs.get("comments", "").strip()

        if status not in ["LGTM", "LBTM"]:
            raise ValueError("Invalid status - must be LGTM or LBTM")

        if status == "LBTM":
            if not comments:
                raise ValueError("Detailed comments required for LBTM status")
            # Format comments as bullet points
            comments = "- " + "\n- ".join(line.strip() for line in comments.split("\n") if line.strip())
        else:
            if comments:
                comments = ""  # Enforce empty comments for LGTM

        return CodeReviewResult(status=status, comments=comments)
