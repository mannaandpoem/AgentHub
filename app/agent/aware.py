from typing import Optional

from pydantic import model_validator

from app.logger import logger

from app.agent import ToolCallAgent
from app.tool import ToolCollection
from app.tool.base import AgentAwareTool


class AwareAgent(ToolCallAgent):
    """Base agent class for handling tool/function calls with enhanced abstraction"""

    name: str = "aware"
    description: str = "an agent that can execute tool calls with aware tool"

    fixed_tools: Optional[ToolCollection] = None

    @model_validator(mode="after")
    def _setup_aware_tools(self) -> "ToolCallAgent":
        """Configure agent-aware tools with reference to this agent."""
        if self.fixed_tools:
            for tool in self.fixed_tools:
                if isinstance(tool, AgentAwareTool):
                    tool.agent = self
        return self

    async def step(self) -> str:
        """Execute a full step: fixed_act + think + act."""
        await self.fixed_act()
        return await super().step()

    async def fixed_act(self) -> str:
        """Execute fixed tool before agent decision"""
        if not self.fixed_tools:
            return ""

        # FIXME: Implement fixed tool execution
        # Execute all tools sequentially
        results = await self.fixed_tools.execute_all()

        # Convert to string format and Log results
        str_results = "\n\n".join([str(r) for r in results])
        logger.info(f"Fixed tool call result: {str_results}")

        return str_results
