import asyncio
import logging
from typing import List, Optional, Union

from browser_use.agent.service import Agent as BrowserAgent
from browser_use.agent.views import AgentHistoryList
from browser_use.controller.service import Controller
from langchain_core.language_models import BaseChatModel
from pydantic import Field

from app.agent import ToolCallAgent
from app.llm import LLM
from app.prompt.operator import NEXT_STEP_PROMPT, SYSTEM_PROMPT
from app.schema import Message, AgentState
from app.tool import ToolCollection, Finish, BaseTool
from app.tool.base import ToolResult
from app.utils.to_langchain_llm import to_langchain_llm

logger = logging.getLogger(__name__)


# Browser Agent Tool Definition
class BrowserAgentTool(BaseTool):
    name: str = "browser_agent"
    description: str = """
    An advanced browser interaction tool that can perform multi-step tasks autonomously.
    Use this tool to navigate websites, interact with elements, extract content, and manage browser state.
    """
    parameters: dict = {
        "type": "object",
        "properties": {
            "task": {
                "type": "string",
                "description": "The task to perform in the browser (e.g., 'find weather in New York')."
            },
            "max_steps": {
                "type": "integer",
                "description": "Maximum number of steps to execute the task (default: 10).",
                "default": 10
            }
        },
        "required": ["task"]
    }

    lock: asyncio.Lock = Field(default_factory=asyncio.Lock)
    agent: BrowserAgent = Field(default=None)
    llm: Union[LLM, BaseChatModel] = Field(default_factory=LLM)
    controller: Controller = Field(default_factory=Controller)

    def init_llm(self, llm: LLM):
        self.llm = BaseChatModel(llm)

    async def _ensure_agent_initialized(self, task: str, max_steps: int) -> BrowserAgent:
        """Initialize or reset the BrowserAgent with the given task."""
        async with self.lock:
            if self.agent is None or self.agent.task != task:
                self.agent = BrowserAgent(
                    task=task,
                    llm=to_langchain_llm(self.llm),
                    browser=self.browser,
                    controller=self.controller,
                    max_actions_per_step=max_steps,
                    **self.kwargs  # Pass additional settings if needed
                )
            return self.agent

    async def execute(self, task: str, max_steps: int = 10, **kwargs) -> ToolResult:
        """
        Execute a browser task using the BrowserAgent.

        Args:
            task: The task to perform
            max_steps: Maximum steps to run the task
            **kwargs: Additional parameters

        Returns:
            ToolResult with the task outcome
        """
        try:
            agent = await self._ensure_agent_initialized(task, max_steps)
            history: AgentHistoryList = await agent.run(max_steps=max_steps)

            if history.is_done():
                final_result = history.final_result()
                success = history.is_successful()
                output = f"Task completed: {final_result}" if success else f"Task unfinished: {final_result}"
                return ToolResult(output=output)
            else:
                errors = history.errors()
                return ToolResult(error=f"Task failed to complete in {max_steps} steps. Errors: {errors}")

        except Exception as e:
            return ToolResult(error=f"Browser agent execution failed: {str(e)}")

    async def cleanup(self):
        """Clean up resources."""
        async with self.lock:
            if self.agent and self.agent.browser:
                await self.agent.browser.close()
            self.agent = None

    def __del__(self):
        """Ensure cleanup on destruction."""
        if self.agent:
            asyncio.run(self.cleanup())


# Enhanced Operator Class
class Operator(ToolCallAgent):
    name: str = "operator"
    description: str = "An agent that can go to the web to perform tasks for you."

    system_prompt: str = SYSTEM_PROMPT
    next_step_prompt: str = NEXT_STEP_PROMPT

    available_tools: ToolCollection = Field(default_factory=lambda: ToolCollection(
        BrowserAgentTool(),  # LLM initialized later
        Finish()
    ))
    special_tool_names: List[str] = Field(default_factory=lambda: [Finish().name])
    max_steps: int = 30


# Example Usage
async def main():
    operator = Operator()
    operator.messages.append(Message.user_message("Please browse the web and find today's weather in New York"))

    while operator.state != AgentState.FINISHED:
        thinking_result = await operator.think()
        if thinking_result:
            result = await operator.act()
            print(f"Agent response: {result}")

    # Cleanup
    for tool in operator.available_tools.tools:
        if isinstance(tool, BrowserAgentTool):
            await tool.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
