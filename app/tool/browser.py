import asyncio
from typing import Literal, Optional

from browsergym.core.action.highlevel import HighLevelActionSet
from browsergym.utils.obs import flatten_axtree_to_str
from pydantic import Field, model_validator

from app.exceptions import BrowserException
from app.runtime.browser_env import BrowserEnv
from app.tool.base import BaseTool, ToolResult


# from browsergym/core/action/highlevel.py
_browser_action_space = HighLevelActionSet(
    subsets=["bid", "nav"],
    strict=False,  # less strict on the parsing of the actions
    multiaction=True,  # enable to agent to take multiple actions at once
)

_BROWSER_DESCRIPTION = """Interact with the browser using Python code. Use it ONLY when you need to interact with a webpage.

See the description of "code" parameter for more details.

Multiple actions can be provided at once, but will be executed sequentially without any feedback from the page.
More than 2-3 actions usually leads to failure or unexpected behavior. Example:
fill('a12', 'example with "quotes"')
click('a51')
click('48', button='middle', modifiers=['Shift'])
"""

_BROWSER_TOOL_DESCRIPTION = """
The following 15 functions are available. Nothing else is supported.

goto(url: str)
    Description: Navigate to a url.
    Examples:
        goto('http://www.example.com')

go_back()
    Description: Navigate to the previous page in history.
    Examples:
        go_back()

go_forward()
    Description: Navigate to the next page in history.
    Examples:
        go_forward()

noop(wait_ms: float = 1000)
    Description: Do nothing, and optionally wait for the given time (in milliseconds).
    You can use this to get the current page content and/or wait for the page to load.
    Examples:
        noop()

        noop(500)

scroll(delta_x: float, delta_y: float)
    Description: Scroll horizontally and vertically. Amounts in pixels, positive for right or down scrolling, negative for left or up scrolling. Dispatches a wheel event.
    Examples:
        scroll(0, 200)

        scroll(-50.2, -100.5)

fill(bid: str, value: str)
    Description: Fill out a form field. It focuses the element and triggers an input event with the entered text. It works for <input>, <textarea> and [contenteditable] elements.
    Examples:
        fill('237', 'example value')

        fill('45', 'multi-line\nexample')

        fill('a12', 'example with "quotes"')

select_option(bid: str, options: str | list[str])
    Description: Select one or multiple options in a <select> element. You can specify option value or label to select. Multiple options can be selected.
    Examples:
        select_option('a48', 'blue')

        select_option('c48', ['red', 'green', 'blue'])

click(bid: str, button: Literal['left', 'middle', 'right'] = 'left', modifiers: list[typing.Literal['Alt', 'Control', 'ControlOrMeta', 'Meta', 'Shift']] = [])
    Description: Click an element.
    Examples:
        click('a51')

        click('b22', button='right')

        click('48', button='middle', modifiers=['Shift'])

dblclick(bid: str, button: Literal['left', 'middle', 'right'] = 'left', modifiers: list[typing.Literal['Alt', 'Control', 'ControlOrMeta', 'Meta', 'Shift']] = [])
    Description: Double click an element.
    Examples:
        dblclick('12')

        dblclick('ca42', button='right')

        dblclick('178', button='middle', modifiers=['Shift'])

hover(bid: str)
    Description: Hover over an element.
    Examples:
        hover('b8')

press(bid: str, key_comb: str)
    Description: Focus the matching element and press a combination of keys. It accepts the logical key names that are emitted in the keyboardEvent.key property of the keyboard events: Backquote, Minus, Equal, Backslash, Backspace, Tab, Delete, Escape, ArrowDown, End, Enter, Home, Insert, PageDown, PageUp, ArrowRight, ArrowUp, F1 - F12, Digit0 - Digit9, KeyA - KeyZ, etc. You can alternatively specify a single character you'd like to produce such as "a" or "#". Following modification shortcuts are also supported: Shift, Control, Alt, Meta, ShiftLeft, ControlOrMeta. ControlOrMeta resolves to Control on Windows and Linux and to Meta on macOS.
    Examples:
        press('88', 'Backspace')

        press('a26', 'ControlOrMeta+a')

        press('a61', 'Meta+Shift+t')

focus(bid: str)
    Description: Focus the matching element.
    Examples:
        focus('b455')

clear(bid: str)
    Description: Clear the input field.
    Examples:
        clear('996')

drag_and_drop(from_bid: str, to_bid: str)
    Description: Perform a drag & drop. Hover the element that will be dragged. Press left mouse button. Move mouse to the element that will receive the drop. Release left mouse button.
    Examples:
        drag_and_drop('56', '498')

upload_file(bid: str, file: str | list[str])
    Description: Click an element and wait for a "filechooser" event, then select one or multiple input files for upload. Relative file paths are resolved relative to the current working directory. An empty list clears the selected files.
    Examples:
        upload_file('572', '/home/user/my_receipt.pdf')

        upload_file('63', ['/home/bob/Documents/image.jpg', '/home/bob/Documents/file.zip'])
"""

for _, action in _browser_action_space.action_set.items():
    assert (
        action.signature in _BROWSER_TOOL_DESCRIPTION
    ), f"Browser description mismatch. Please double check if the BrowserGym updated their action space.\n\nAction: {action.signature}"
    assert (
        action.description in _BROWSER_TOOL_DESCRIPTION
    ), f"Browser description mismatch. Please double check if the BrowserGym updated their action space.\n\nAction: {action.description}"


class BrowserOutput(ToolResult):
    output: Optional[str] = Field(default=None)
    error: Optional[str] = Field(default=None)

    url: Optional[str] = Field(default=None)
    trigger_by_action: Literal["browse", "browse_interactive"] = Field(
        default="browse_interactive"
    )
    screenshot: Optional[str] = Field(
        default=None, description="Base64 encoded screenshot", repr=False
    )

    # do not include in the memory
    open_pages_urls: list = Field(default_factory=list)
    active_page_index: int = -1
    dom_object: dict = Field(default_factory=dict, repr=False)  # don't show in repr
    axtree_object: dict = Field(default_factory=dict, repr=False)  # don't show in repr
    extra_element_properties: dict = Field(
        default_factory=dict, repr=False
    )  # don't show in repr
    last_browser_action: str = ""
    last_browser_action_error: str = ""
    focused_element_bid: str = ""

    browsergym_message: Optional[str] = Field(default=None)

    @property
    def message(self) -> str:
        return "Visited " + self.url

    def __str__(self) -> str:
        ret = (
            "**Browser Output**\n"
            f"URL: {self.url}\n"
            f"Error: {self.error}\n"
            f"Open pages: {self.open_pages_urls}\n"
            f"Active page index: {self.active_page_index}\n"
            f"Last browser action: {self.last_browser_action}\n"
            f"Last browser action error: {self.last_browser_action_error}\n"
            f"Focused element bid: {self.focused_element_bid}\n"
        )
        ret += "--- Agent Observation ---\n"
        ret += self.get_agent_obs_text()
        return ret

    def get_agent_obs_text(self) -> str:
        """Get a concise text that will be shown to the agent."""
        if self.trigger_by_action == "browse_interactive":
            text = f"[Current URL: {self.url}]\n"
            text += f"[Focused element bid: {self.focused_element_bid}]\n\n"
            if self.error:
                text += (
                    "================ BEGIN error message ===============\n"
                    "The following error occurred when executing the last action:\n"
                    f"{self.last_browser_action_error}\n"
                    "================ END error message ===============\n"
                )
            else:
                text += "[Action executed successfully.]\n"
            try:
                # We do not filter visible only here because we want to show the full content
                # of the web page to the agent for simplicity.
                # FIXME: handle the case when the web page is too large
                cur_axtree_txt = self.get_axtree_str(filter_visible_only=False)
                text += (
                    f"============== BEGIN accessibility tree ==============\n"
                    f"{cur_axtree_txt}\n"
                    f"============== END accessibility tree ==============\n"
                )
            except Exception as e:
                text += (
                    f"\n[Error encountered when processing the accessibility tree: {e}]"
                )
            return text

        elif self.trigger_by_action == "browse":
            text = f"[Current URL: {self.url}]\n"
            if self.error:
                text += (
                    "================ BEGIN error message ===============\n"
                    "The following error occurred when trying to visit the URL:\n"
                    f"{self.last_browser_action_error}\n"
                    "================ END error message ===============\n"
                )
            text += "============== BEGIN webpage content ==============\n"
            text += self.content
            text += "\n============== END webpage content ==============\n"
            return text
        else:
            raise ValueError(f"Invalid trigger_by_action: {self.trigger_by_action}")

    def get_axtree_str(self, filter_visible_only: bool = False) -> str:
        cur_axtree_txt = flatten_axtree_to_str(
            self.axtree_object,
            extra_properties=self.extra_element_properties,
            with_clickable=True,
            skip_generic=False,
            filter_visible_only=filter_visible_only,
        )
        return cur_axtree_txt


class Browser(BaseTool):
    name: str = "browser"
    description: str = _BROWSER_DESCRIPTION
    parameters: dict = {
        "type": "object",
        "properties": {
            "code": {
                "type": "string",
                "description": (
                    "The Python code that interacts with the browser.\n"
                    + _BROWSER_TOOL_DESCRIPTION
                ),
            }
        },
        "required": ["code"],
    }

    browser: Optional[BrowserEnv] = None
    lock: asyncio.Lock = Field(default_factory=asyncio.Lock)
    trigger_by_action: Literal["browse_interactive"] = Field(
        default="browse_interactive"
    )

    @model_validator(mode="after")
    def _initialize_browser(self):
        """Initialize browser with error handling"""
        if self.browser is None:
            try:
                self.browser = BrowserEnv()
            except ImportError as e:
                raise BrowserException(
                    f"Browser environment initialization failed: {str(e)}"
                )
        return self

    async def execute(self, code: str) -> BrowserOutput:
        """Execute browser actions with improved error handling and state management"""
        async with self.lock:
            try:
                if self.browser is None:
                    raise BrowserException("Browser environment is not available")

                # Execute browser code
                obs = self.browser.step(code)

                # Create enhanced observation
                result = BrowserOutput(
                    output=obs.get("text_content", ""),
                    error=obs.get("last_action_error"),
                    url=obs.get("url", ""),
                    trigger_by_action=self.trigger_by_action,
                    screenshot=obs.get(
                        "screenshot", None
                    ),  # base64-encoded screenshot, png
                    open_pages_urls=obs.get(
                        "open_pages_urls", []
                    ),  # list of open pages
                    active_page_index=obs.get(
                        "active_page_index", -1
                    ),  # index of the active page
                    dom_object=obs.get("dom_object", {}),  # DOM object
                    axtree_object=obs.get(
                        "axtree_object", {}
                    ),  # accessibility tree object
                    extra_element_properties=obs.get("extra_element_properties", {}),
                    focused_element_bid=obs.get(
                        "focused_element_bid", None
                    ),  # focused element bid
                    last_browser_action=obs.get(
                        "last_action", ""
                    ),  # last browser env action performed
                    last_browser_action_error=obs.get("last_action_error", ""),
                    browsergym_message=obs.get("browsergym_message", ""),
                )

                return result

            except Exception as e:
                return BrowserOutput(error=f"Browser execution failed: {str(e)}")

    def close(self):
        """Clean up browser resources"""
        if self.browser is not None:
            self.browser.close()
            self.browser = None

    async def __aenter__(self):
        """Async context manager support"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Cleanup on exit"""
        self.close()


async def main():
    async with Browser() as browser:
        result = await browser.execute('goto("https://example.com")\nnoop(1000)')
        print(result)


if __name__ == "__main__":
    asyncio.run(main())
