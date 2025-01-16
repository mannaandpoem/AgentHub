from abc import ABC, abstractmethod
from enum import Enum
from typing import Any

from pydantic import BaseModel

from app.agent.toolcall import ToolCallAgent
from app.tool import ToolCollection


class Node(BaseModel):
    node_id: Any


class FlowType(str, Enum):
    BASIC = "basic"
    MCTS = "mcts"
    AFLOW = "aflow"


class BaseFlow(ABC):
    def __init__(self, agent: ToolCallAgent, tools: ToolCollection):
        self.agent = agent
        self.tools = tools
        self._setup_agent()

    def _setup_agent(self):
        """Configure agent with tools and initial setup"""
        if isinstance(self.agent, ToolCallAgent):
            if self.tools:
                self.agent.available_tools = self.tools

    @abstractmethod
    async def execute(self, input_text: str) -> str:
        """Execute the flow with given input"""
