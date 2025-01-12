from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from app.tool.base import BaseTool


@dataclass
class SearchResult:
    file: str
    line: int
    match_line: str
    before_context: List[str]
    after_context: List[str]

    @classmethod
    def format_results(cls, results: List["SearchResult"], directory_path: str) -> str:
        MAX_RESULTS = 250
        output = []

        if len(results) >= MAX_RESULTS:
            output.append(
                f"Showing first {MAX_RESULTS} of {MAX_RESULTS}+ results. Use a more specific search if necessary.\n"
            )
        else:
            result_text = "1 result" if len(results) == 1 else f"{len(results)} results"
            output.append(f"Found {result_text}.\n")

        # Group results by file
        grouped_results = {}
        for result in results[:MAX_RESULTS]:
            file_path = Path(directory_path) / result.file
            if file_path not in grouped_results:
                grouped_results[file_path] = []
            grouped_results[file_path].append(result)

        # Format results
        for file_path, file_results in grouped_results.items():
            output.append(f"{file_path}\n│----")

            for idx, result in enumerate(file_results):
                all_lines = (
                    result.before_context + [result.match_line] + result.after_context
                )
                for line in all_lines:
                    output.append(f"│{line.rstrip()}")

                if idx < len(file_results) - 1:
                    output.append("│----")

            output.append("│----\n")

        return "\n".join(output).rstrip()


class SearchFile(BaseTool):
    name: str = "search_files"
    description: str = """
    Request to perform a regex search across files in a specified directory, providing context-rich results.
    This tool searches for patterns or specific content across multiple files, displaying each match with encapsulating context.
    """
    parameters: dict = {
        "type": "object",
        "properties": {
            "directory_path": {
                "type": "string",
                "description": "(required) The absolute path of the directory to search in. This directory will be recursively searched.",
            },
            "regex_pattern": {
                "type": "string",
                "description": "(required) The regular expression pattern to search for. Uses Python regex syntax.",
            },
            "file_pattern": {
                "type": "string",
                "description": "(optional) Glob pattern to filter files (e.g., '*.ts' for TypeScript files). If not provided, it will search all files (*).",
            },
        },
        "required": ["directory_path", "regex_pattern"],
    }

    async def execute(
        self,
        directory_path: str,
        regex_pattern: str,
        file_pattern: Optional[str] = None,
    ) -> str:
        import re
        from pathlib import Path

        file_pattern = file_pattern or "*"
        results = []
        directory = Path(directory_path)

        for file_path in directory.rglob(file_pattern):
            if not file_path.is_file():
                continue

            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    lines = f.readlines()

                for i, line in enumerate(lines):
                    if re.search(regex_pattern, line):
                        before_context = lines[max(0, i - 1) : i]
                        after_context = lines[i + 1 : i + 2]

                        results.append(
                            SearchResult(
                                file=str(file_path.relative_to(directory)),
                                line=i + 1,
                                match_line=line,
                                before_context=before_context,
                                after_context=after_context,
                            )
                        )
            except (UnicodeDecodeError, IOError):
                continue  # Skip files that can't be read

        return SearchResult.format_results(results, directory_path)

    @staticmethod
    def get_evaluation_criteria(trajectory_length: int) -> List[str]:
        base_criteria = [
            "Query Relevance: Evaluate if the search query or parameters are well-defined and likely to find relevant code.",
            "Search Scope Appropriateness: Check if the file patterns and class/function names narrow down the search effectively.",
            "Relevance of Search Results: Assess whether the search results are directly related to the problem and useful for making progress.",
            "Size of Search Results: Ensure that the code context provided is appropriately sized—not too large to overwhelm nor too small to be unhelpful.",
        ]

        if trajectory_length < 3:
            return [
                "Exploratory Actions: Recognize that initial searches and information-gathering steps are essential.",
                "Appropriateness of Action: Evaluate if the action is logical given the current knowledge.",
            ] + base_criteria

        return [
            "Solution Quality: Assess the logical changes, contextual fit, and overall improvement.",
            "Progress Assessment: Evaluate awareness of solution history and planned next steps.",
            "Repetitive Actions: Detect if repeating unsuccessful actions without progress.",
        ] + base_criteria
