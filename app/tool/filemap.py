import warnings
from typing import Any, Dict, Optional

from tree_sitter_languages import get_language, get_parser

from app.tool.base import BaseTool


class Filemap(BaseTool):
    name: str = "filemap"
    description: str = "Print the contents of a Python file, skipping lengthy function and method definitions."
    parameters: Optional[Dict[str, Any]] = {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "The path to the Python file to be read.",
            }
        },
        "required": ["file_path"],
    }

    async def execute(self, file_path: str) -> str:
        """
        Execute the filemap tool.

        Args:
            file_path (str): The path to the Python file to be read.

        Returns:
            str: The processed content of the file with lengthy functions/methods elided.
        """
        # Suppress FutureWarnings from tree_sitter
        warnings.simplefilter("ignore", category=FutureWarning)

        # Initialize the parser for Python
        parser = get_parser("python")
        language = get_language("python")

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                file_contents = f.read()
        except FileNotFoundError:
            return f"Error: The file '{file_path}' does not exist."
        except IOError as e:
            return f"IOError while reading the file: {e}"

        # Parse the file contents
        tree = parser.parse(bytes(file_contents, "utf8"))

        # Define a query to find function and method definitions
        # This includes both standalone functions and methods within classes
        query = language.query(
            """
        (
            function_definition
            name: (identifier) @func_name
            body: (block) @body
        )
        (
            class_definition
            body: (block) @class_body
        )
        """
        )

        captures = query.captures(tree.root_node)
        elide_line_ranges = []

        for node, capture_name in captures:
            if capture_name == "body":
                # Calculate the number of lines in the function/method body
                start_line = node.start_point[0]
                end_line = node.end_point[0]
                num_lines = end_line - start_line + 1
                if num_lines >= 5:
                    elide_line_ranges.append((start_line, end_line))
            elif capture_name == "class_body":
                # Optionally, handle class body if needed
                pass  # Currently not eliding entire classes

        if not elide_line_ranges:
            # No functions/methods met the elision criteria
            return file_contents

        # Merge overlapping or consecutive ranges
        elide_line_ranges = self.merge_ranges(elide_line_ranges)

        # Create a set of lines to elide and messages
        elide_messages = {
            start: f"... eliding lines {start+1}-{end+1} ..."
            for start, end in elide_line_ranges
        }
        elide_lines = set()
        for start, end in elide_line_ranges:
            for line in range(start, end + 1):
                elide_lines.add(line)

        processed_lines = []
        i = 0
        total_lines = file_contents.splitlines()

        while i < len(total_lines):
            if i in elide_messages:
                # Insert the elision message
                processed_lines.append(f"{i+1:6d} {elide_messages[i]}")
                # Skip the elided lines
                # Find the end of this elision range
                for start, end in elide_line_ranges:
                    if start == i:
                        i = end + 1
                        break
            elif i in elide_lines:
                # This line is part of an elided range but not the start; skip it
                i += 1
            else:
                # Regular line
                processed_lines.append(f"{i+1:6d} {total_lines[i]}")
                i += 1

        return "\n".join(processed_lines)

    @staticmethod
    def merge_ranges(ranges):
        """
        Merge overlapping or consecutive line ranges.

        Args:
            ranges (List[Tuple[int, int]]): List of (start, end) line ranges.

        Returns:
            List[Tuple[int, int]]: Merged list of line ranges.
        """
        if not ranges:
            return []

        # Sort ranges by start line
        sorted_ranges = sorted(ranges, key=lambda x: x[0])
        merged = [sorted_ranges[0]]

        for current in sorted_ranges[1:]:
            last = merged[-1]
            if current[0] <= last[1] + 1:
                # Overlapping or consecutive ranges; merge them
                merged[-1] = (last[0], max(last[1], current[1]))
            else:
                merged.append(current)

        return merged
