from pydantic import BaseModel

from app.tool import BaseTool

obtain_relevant_files_prompt = """
Please look through the following GitHub problem description and Repository structure and provide a list of files that one would need to edit to fix the problem.

### GitHub Problem Description ###
{problem_statement}

###

### Repository Structure ###
{structure}

###

Please only provide the full path and return at most 5 files.
"""


class FileLevelLocalization(BaseTool):
    name: str = "file_level_localization"
    description: str = "Analyzes a problem description and repository structure to identify up to 5 files that likely need to be modified to fix the issue."
    parameters: dict = {
        "type": "object",
        "properties": {
            "file_list": {
                "type": "array",
                "description": "List of file paths (maximum 5) that need to be modified to fix the problem",
                "items": {
                    "type": "string",
                    "description": "Full path to a file in the repository"
                },
                "maxItems": 5
            }
        },
        "required": ["file_list"]
    }

    async def execute(self, file_list: list) -> dict:
        return {"file_list": file_list}
