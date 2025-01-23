import asyncio
from typing import Literal, Optional

from browsergym.core.action.highlevel import HighLevelActionSet
from browsergym.utils.obs import flatten_axtree_to_str
from pydantic import Field, model_validator

from app.tool.base import BaseTool, ToolResult

import atexit
import base64
import io
import json
import multiprocessing
import time
import uuid

import browsergym.core  # noqa F401 (we register the openended task as a gym environment)
import gymnasium as gym
import html2text
import numpy as np
import tenacity
from browsergym.utils.obs import flatten_dom_to_str
from PIL import Image

from app.exceptions import BrowserException
from app.logger import logger
from app.utils.shutdown_listener import should_continue, should_exit

BROWSER_EVAL_GET_GOAL_ACTION = "GET_EVAL_GOAL"
BROWSER_EVAL_GET_REWARDS_ACTION = "GET_EVAL_REWARDS"


class BrowserEnv:
    def __init__(self, browsergym_eval_env: str | None = None):
        self.html_text_converter = self.get_html_text_converter()
        self.eval_mode = False
        self.eval_dir = ""

        # EVAL only: browsergym_eval_env must be provided for evaluation
        self.browsergym_eval_env = browsergym_eval_env
        self.eval_mode = bool(browsergym_eval_env)

        # Initialize browser environment process
        multiprocessing.set_start_method("spawn", force=True)
        self.browser_side, self.agent_side = multiprocessing.Pipe()

        self.init_browser()
        atexit.register(self.close)

    def get_html_text_converter(self):
        html_text_converter = html2text.HTML2Text()
        # ignore links and images
        html_text_converter.ignore_links = False
        html_text_converter.ignore_images = True
        # use alt text for images
        html_text_converter.images_to_alt = True
        # disable auto text wrapping
        html_text_converter.body_width = 0
        return html_text_converter

    @tenacity.retry(
        wait=tenacity.wait_fixed(1),
        stop=tenacity.stop_after_attempt(5),
        retry=tenacity.retry_if_exception_type(BrowserException),
    )
    def init_browser(self):
        logger.debug("Starting browser env...")
        try:
            self.process = multiprocessing.Process(target=self.browser_process)
            self.process.start()
        except Exception as e:
            logger.error(f"Failed to start browser process: {e}")
            raise

        if not self.check_alive():
            self.close()
            raise BrowserException("Failed to start browser environment.")

    def browser_process(self):
        if self.eval_mode:
            assert self.browsergym_eval_env is not None
            logger.debug("Initializing browser env for web browsing evaluation.")
            if "webarena" in self.browsergym_eval_env:
                import browsergym.webarena  # noqa F401 register webarena tasks as gym environments
            elif "miniwob" in self.browsergym_eval_env:
                import browsergym.miniwob  # noqa F401 register miniwob tasks as gym environments
            else:
                raise ValueError(
                    f"Unsupported browsergym eval env: {self.browsergym_eval_env}"
                )
            env = gym.make(
                self.browsergym_eval_env,
                tags_to_mark="all",
            )
        else:
            env = gym.make(
                "browsergym/openended",
                task_kwargs={"start_url": "about:blank", "goal": "PLACEHOLDER_GOAL"},
                wait_for_user_message=False,
                headless=True,
                disable_env_checker=True,
                tags_to_mark="all",
            )

        obs, info = env.reset()

        # EVAL ONLY: save the goal into file for evaluation
        self.eval_goal = None
        self.eval_rewards: list[float] = []
        if self.eval_mode:
            logger.debug(f"Browsing goal: {obs['goal']}")
            self.eval_goal = obs["goal"]

        logger.debug("Browser env started.")
        while should_continue():
            try:
                if self.browser_side.poll(timeout=0.01):
                    unique_request_id, action_data = self.browser_side.recv()

                    # shutdown the browser environment
                    if unique_request_id == "SHUTDOWN":
                        logger.debug("SHUTDOWN recv, shutting down browser env...")
                        env.close()
                        return
                    elif unique_request_id == "IS_ALIVE":
                        self.browser_side.send(("ALIVE", None))
                        continue

                    # EVAL ONLY: Get evaluation info
                    if action_data["action"] == BROWSER_EVAL_GET_GOAL_ACTION:
                        self.browser_side.send(
                            (unique_request_id, {"text_content": self.eval_goal})
                        )
                        continue
                    elif action_data["action"] == BROWSER_EVAL_GET_REWARDS_ACTION:
                        self.browser_side.send(
                            (
                                unique_request_id,
                                {"text_content": json.dumps(self.eval_rewards)},
                            )
                        )
                        continue

                    action = action_data["action"]
                    obs, reward, terminated, truncated, info = env.step(action)

                    # EVAL ONLY: Save the rewards into file for evaluation
                    if self.eval_mode:
                        self.eval_rewards.append(reward)

                    # add text content of the page
                    html_str = flatten_dom_to_str(obs["dom_object"])
                    obs["text_content"] = self.html_text_converter.handle(html_str)
                    # make observation serializable
                    obs["screenshot"] = self.image_to_png_base64_url(obs["screenshot"])
                    obs["active_page_index"] = obs["active_page_index"].item()
                    obs["elapsed_time"] = obs["elapsed_time"].item()
                    self.browser_side.send((unique_request_id, obs))
            except KeyboardInterrupt:
                logger.debug("Browser env process interrupted by user.")
                try:
                    env.close()
                except Exception:
                    pass
                return

    def step(self, action_str: str, timeout: float = 30) -> dict:
        """Execute an action in the browser environment and return the observation."""
        unique_request_id = str(uuid.uuid4())
        self.agent_side.send((unique_request_id, {"action": action_str}))
        start_time = time.time()
        while True:
            if should_exit() or time.time() - start_time > timeout:
                raise TimeoutError("Browser environment took too long to respond.")
            if self.agent_side.poll(timeout=0.01):
                response_id, obs = self.agent_side.recv()
                if response_id == unique_request_id:
                    return obs

    def check_alive(self, timeout: float = 60):
        self.agent_side.send(("IS_ALIVE", None))
        if self.agent_side.poll(timeout=timeout):
            response_id, _ = self.agent_side.recv()
            if response_id == "ALIVE":
                return True
            logger.debug(f"Browser env is not alive. Response ID: {response_id}")

    def close(self):
        if not self.process.is_alive():
            return
        try:
            self.agent_side.send(("SHUTDOWN", None))
            self.process.join(5)  # Wait for the process to terminate
            if self.process.is_alive():
                logger.error(
                    "Browser process did not terminate, forcefully terminating..."
                )
                self.process.terminate()
                self.process.join(5)  # Wait for the process to terminate
                if self.process.is_alive():
                    self.process.kill()
                    self.process.join(5)  # Wait for the process to terminate
            self.agent_side.close()
            self.browser_side.close()
        except Exception:
            logger.error("Encountered an error when closing browser env", exc_info=True)

    @staticmethod
    def image_to_png_base64_url(
            image: np.ndarray | Image.Image, add_data_prefix: bool = False
    ):
        """Convert a numpy array to a base64 encoded png image url."""
        if isinstance(image, np.ndarray):
            image = Image.fromarray(image)
        if image.mode in ("RGBA", "LA"):
            image = image.convert("RGB")
        buffered = io.BytesIO()
        image.save(buffered, format="PNG")

        image_base64 = base64.b64encode(buffered.getvalue()).decode()
        return (
            f"data:image/png;base64,{image_base64}"
            if add_data_prefix
            else f"{image_base64}"
        )

    @staticmethod
    def image_to_jpg_base64_url(
            image: np.ndarray | Image.Image, add_data_prefix: bool = False
    ):
        """Convert a numpy array to a base64 encoded jpeg image url."""
        if isinstance(image, np.ndarray):
            image = Image.fromarray(image)
        if image.mode in ("RGBA", "LA"):
            image = image.convert("RGB")
        buffered = io.BytesIO()
        image.save(buffered, format="JPEG")

        image_base64 = base64.b64encode(buffered.getvalue()).decode()
        return (
            f"data:image/jpeg;base64,{image_base64}"
            if add_data_prefix
            else f"{image_base64}"
        )


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
