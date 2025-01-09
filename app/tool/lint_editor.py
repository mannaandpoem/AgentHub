#!/usr/bin/env python3

import sys
from typing import Any, ClassVar, Dict, Optional

from app.tool.tool import Tool


# Import necessary modules; adjust the import paths as needed
try:
    from sweagent import TOOLS_DIR
except ImportError:
    TOOLS_DIR = None  # Handle accordingly if TOOLS_DIR is not available

if TOOLS_DIR:
    default_lib = TOOLS_DIR / "defaults" / "lib"
    assert default_lib.is_dir(), f"Default library directory not found: {default_lib}"
    sys.path.append(str(default_lib))
    sys.path.append(str(TOOLS_DIR / "registry" / "lib"))

from flake8_utils import flake8, format_flake8_output  # type: ignore
from windowed_file import FileNotOpened, WindowedFile  # type: ignore


# Assuming these classes are defined elsewhere in your environment
# from some_module import ChatCompletionToolParam, FunctionDefinition  # Adjust the import as necessary


class EditorTool(Tool):
    name: ClassVar[str] = "edit"
    description: ClassVar[
        str
    ] = """
Replaces lines <start_line> through <end_line> (inclusive) with the given text in the open file.
All of the <replacement text> will be entered, so make sure your indentation is formatted properly.
Please note that THIS COMMAND REQUIRES PROPER INDENTATION.
If you'd like to add the line '        print(x)' you must fully write that out, with all those spaces before the code!
"""
    parameters: ClassVar[Optional[Dict[str, Any]]] = {
        "type": "object",
        "properties": {
            "start_line": {
                "type": "integer",
                "description": "The line number to start the edit at",
                "required": True,
            },
            "end_line": {
                "type": "integer",
                "description": "The line number to end the edit at (inclusive)",
                "required": True,
            },
            "replacement_text": {
                "type": "string",
                "description": "The text to replace the current selection with",
                "required": True,
            },
        },
        "required": ["start_line", "end_line", "replacement_text"],
    }

    def execute(self, **kwargs):
        """
        Executes the edit operation.

        Expected kwargs:
            start_line (int): The line number to start the edit at.
            end_line (int): The line number to end the edit at (inclusive).
            replacement_text (str): The text to replace the selected lines with.
        """
        # Define messages
        _EDIT_SUCCESS_MSG = (
            "File updated. Please review the changes and make sure they are correct "
            "(correct indentation, no duplicate lines, etc). Edit the file again if necessary."
        )

        _LINT_ERROR_TEMPLATE = """Your proposed edit has introduced new syntax error(s). Please read this error message carefully and then retry editing the file.

ERRORS:
{errors}

This is how your edit would have looked if applied
------------------------------------------------
{window_applied}
------------------------------------------------

This is the original code before your edit
------------------------------------------------
{window_original}
------------------------------------------------

Your changes have NOT been applied. Please fix your edit command and try again.
DO NOT re-run the same failed edit command. Running it again will lead to the same error."""

        # Extract parameters
        start_line = kwargs.get("start_line")
        end_line = kwargs.get("end_line")
        replacement_text = kwargs.get("replacement_text")

        # Validate parameters
        if not isinstance(start_line, int) or not isinstance(end_line, int):
            raise ValueError("start_line and end_line must be integers.")
        if not isinstance(replacement_text, str):
            raise ValueError("replacement_text must be a string.")

        # Handle file opening
        try:
            wf = WindowedFile(exit_on_exception=False)
        except FileNotOpened:
            print("No file opened. Use the `open` command first.")
            sys.exit(1)

        # Adjust for zero-based indexing
        start_idx, end_idx = start_line - 1, end_line - 1

        # Prepare replacement text
        replacement_text = replacement_text.rstrip("\n")

        # Get pre-edit linting errors
        pre_edit_lint = flake8(wf.path)

        # Perform the edit
        try:
            wf.set_window_text(replacement_text, line_range=(start_idx, end_idx))
        except Exception as e:
            print(f"Failed to apply edit: {e}")
            sys.exit(1)

        # Check for new linting errors
        post_edit_lint = flake8(wf.path)
        new_flake8_output = format_flake8_output(
            post_edit_lint,
            previous_errors_string=pre_edit_lint,
            replacement_window=(start_idx, end_idx),
            replacement_n_lines=len(replacement_text.splitlines()),
        )

        if new_flake8_output:
            # Show error and revert changes
            try:
                with_edits = wf.get_window_text(
                    line_numbers=True, status_line=True, pre_post_line=True
                )
                wf.undo_edit()
                without_edits = wf.get_window_text(
                    line_numbers=True, status_line=True, pre_post_line=True
                )
            except Exception as e:
                print(f"Failed to retrieve window text: {e}")
                sys.exit(1)

            print(
                _LINT_ERROR_TEMPLATE.format(
                    errors=new_flake8_output,
                    window_applied=with_edits,
                    window_original=without_edits,
                )
            )
            sys.exit(1)

        # Success - update window position and show result
        try:
            wf.goto(start_idx, mode="top")
            print(_EDIT_SUCCESS_MSG)
            wf.print_window()
        except Exception as e:
            print(f"Failed to update window view: {e}")
            sys.exit(1)


# Example usage:
# Assuming you have a mechanism to register and invoke tools
if __name__ == "__main__":
    import argparse

    def main():
        parser = argparse.ArgumentParser(description="Editor Tool")
        parser.add_argument(
            "start_line", type=int, help="The line number to start the edit at"
        )
        parser.add_argument(
            "end_line", type=int, help="The line number to end the edit at (inclusive)"
        )
        parser.add_argument(
            "replacement_text",
            type=str,
            help="The text to replace the current selection with",
        )
        args = parser.parse_args()

        editor_tool = EditorTool()
        editor_tool.execute(
            start_line=args.start_line,
            end_line=args.end_line,
            replacement_text=args.replacement_text,
        )

    main()
