import json
import re
import sys
import threading
import traceback
from io import StringIO
from typing import Dict, Any, Optional, List
from uuid import uuid4

from app.tool.base import BaseTool, ToolResult

_EXECUTION_IPYNB_CODE_DESCRIPTION = """\
Executes Python code in Jupyter notebook style, maintaining state between executions. Supports code cells, markdown cells, and rich outputs.
"""


class ExecuteIpynbCode(BaseTool):
    """A tool for executing Jupyter notebook-style Python code with state persistence between calls."""

    name: str = "execute_ipynb_code"
    description: str = _EXECUTION_IPYNB_CODE_DESCRIPTION
    parameters: dict = {
        "type": "object",
        "properties": {
            "code": {
                "type": "string",
                "description": "The Python code to execute or markdown text to render.",
            },
            "cell_type": {
                "type": "string",
                "enum": ["code", "markdown"],
                "description": "The type of cell to execute. Defaults to 'code'.",
                "default": "code"
            },
            "session_id": {
                "type": "string",
                "description": "Optional session ID to maintain state between executions. If not provided, a new session will be created.",
            },
            "clear_session": {
                "type": "boolean",
                "description": "If true, clears the session state. Defaults to false.",
                "default": False
            },
        },
        "required": ["code"],
    }

    # Class-level storage for maintaining session state
    _sessions: Dict[str, Dict[str, Any]] = {}

    timeout: int = 50

    def _get_or_create_session(self, session_id: Optional[str] = None) -> str:
        """Get an existing session or create a new one."""
        if not session_id:
            session_id = str(uuid4())

        if session_id not in self._sessions:
            # Create a safe globals dictionary with builtins
            safe_globals = {"__builtins__": __builtins__}

            self._sessions[session_id] = {
                "globals": safe_globals,
                "locals": {},
                "history": []
            }

        return session_id

    def _clear_session(self, session_id: str) -> None:
        """Clear a session's state."""
        if session_id in self._sessions:
            # Create a safe globals dictionary with builtins
            safe_globals = {"__builtins__": __builtins__}

            self._sessions[session_id] = {
                "globals": safe_globals,
                "locals": {},
                "history": []
            }

    def _capture_display_data(self, output: List[Dict], globals_dict: Dict) -> None:
        """Capture display data from IPython display objects if present."""
        # Check if IPython display has been imported and used
        if '_ipython_display_' in globals_dict:
            # This is a simplified implementation
            # In a real implementation, you would capture the rich display data
            output.append({
                "output_type": "display_data",
                "data": {"text/plain": "Rich display output captured"}
            })

    def _execute_code_cell(self, code: str, session_id: str, timeout: int) -> Dict:
        """Execute a code cell and return the results."""
        session = self._sessions[session_id]
        result = {
            "cell_type": "code",
            "execution_count": len(session["history"]) + 1,
            "outputs": [],
            "source": code,
            "error": None,
            "success": True
        }

        def run_code():
            try:
                # Capture stdout
                stdout_buffer = StringIO()
                stderr_buffer = StringIO()
                old_stdout, old_stderr = sys.stdout, sys.stderr
                sys.stdout, sys.stderr = stdout_buffer, stderr_buffer

                try:
                    # Execute the code
                    exec_result = exec(code, session["globals"], session["locals"])

                    # Capture standard output
                    stdout_content = stdout_buffer.getvalue()
                    if stdout_content:
                        result["outputs"].append({
                            "output_type": "stream",
                            "name": "stdout",
                            "text": stdout_content
                        })

                    # Capture standard error
                    stderr_content = stderr_buffer.getvalue()
                    if stderr_content:
                        result["outputs"].append({
                            "output_type": "stream",
                            "name": "stderr",
                            "text": stderr_content
                        })

                    # Try to capture the last expression result (like Jupyter does)
                    if code.strip() and not code.strip().endswith(';'):
                        last_expr = code.strip().split('\n')[-1].strip()
                        if re.match(r'^[a-zA-Z0-9_]+$', last_expr) and last_expr in session["locals"]:
                            result["outputs"].append({
                                "output_type": "execute_result",
                                "execution_count": result["execution_count"],
                                "data": {"text/plain": repr(session["locals"][last_expr])}
                            })

                    # Capture any display data (if IPython-like functionality is used)
                    self._capture_display_data(result["outputs"], session["globals"])

                finally:
                    # Restore stdout/stderr
                    sys.stdout, sys.stderr = old_stdout, old_stderr

            except Exception as e:
                result["error"] = {
                    "ename": type(e).__name__,
                    "evalue": str(e),
                    "traceback": traceback.format_exc()
                }
                result["success"] = False
                result["outputs"].append({
                    "output_type": "error",
                    "ename": type(e).__name__,
                    "evalue": str(e),
                    "traceback": traceback.format_exc().split('\n')
                })

        # Run in separate thread with timeout
        thread = threading.Thread(target=run_code)
        thread.start()
        thread.join(timeout)

        if thread.is_alive():
            result["error"] = {
                "ename": "TimeoutError",
                "evalue": f"Execution timeout after {timeout} seconds",
                "traceback": "Execution timed out"
            }
            result["success"] = False
            result["outputs"].append({
                "output_type": "error",
                "ename": "TimeoutError",
                "evalue": f"Execution timeout after {timeout} seconds",
                "traceback": [f"Execution timed out after {timeout} seconds"]
            })

        # Add the execution to history
        session["history"].append(result)

        return result

    def _render_markdown_cell(self, markdown: str, session_id: str) -> Dict:
        """Process a markdown cell and return the results."""
        session = self._sessions[session_id]
        result = {
            "cell_type": "markdown",
            "execution_count": None,
            "source": markdown,
            "error": None,
            "success": True
        }

        # Add the markdown to history
        session["history"].append(result)

        return result

    async def execute(
            self,
            code: str,
            cell_type: str = "code",
            session_id: Optional[str] = None,
            clear_session: bool = False,
            timeout: Optional[int] = None
    ) -> ToolResult:
        """
        Executes the provided code in a Jupyter notebook-style environment.

        Args:
            code (str): The code to execute or markdown to render.
            cell_type (str): The type of cell ('code' or 'markdown'). Defaults to 'code'.
            session_id (Optional[str]): Session ID for maintaining state between executions.
            clear_session (bool): Whether to clear the session state before execution.
            timeout (Optional[int]): Execution timeout in seconds. Defaults to the tool's timeout.

        Returns:
            ToolResult: Contains execution results, outputs, and status information.
        """
        if timeout is None:
            timeout = self.timeout

        # Get or create session
        session_id = self._get_or_create_session(session_id)

        # Clear session if requested
        if clear_session:
            self._clear_session(session_id)

        # Execute based on cell type
        if cell_type.lower() == "markdown":
            result = self._render_markdown_cell(code, session_id)
        else:
            result = self._execute_code_cell(code, session_id, timeout)

        # Add session_id to result
        result["session_id"] = session_id

        # Format the response for the tool result
        tool_result = ToolResult(
            output=json.dumps(result, default=str),
            error=json.dumps(result["error"]) if result["error"] else None,
            system=None
        )

        return tool_result
