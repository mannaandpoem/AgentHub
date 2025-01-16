class ToolError(Exception):
    """Raised when a tool encounters an error."""

    def __init__(self, message):
        self.message = message


class BrowserException(Exception):
    """Base exception for browser-related errors."""

    def __init__(self, message):
        super().__init__(message)
