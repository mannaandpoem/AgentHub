import asyncio
from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from typing import Any, List, Optional

from pydantic import BaseModel, Field, model_validator

from app.llm import LLM
from app.logger import logger
from app.schema import AgentState, Memory, Message


class BaseAgent(BaseModel, ABC):
    """Abstract base agent class for managing agent state and execution"""

    name: str
    description: Optional[str] = None

    system_prompt: Optional[str] = None
    next_step_prompt: Optional[str] = None

    llm: Optional[LLM] = Field(default_factory=LLM)
    memory: Memory = Field(default_factory=Memory)
    state: AgentState = AgentState.IDLE

    max_steps: int = 10
    current_step: int = 0

    class Config:
        arbitrary_types_allowed = True
        extra = "allow"

    @model_validator(mode="after")
    def initialize_agent(self) -> "BaseAgent":
        """Initialize agent with default settings"""
        if self.llm is None:
            self.llm = LLM(config_name=self.name.lower())
        return self

    @asynccontextmanager
    async def state_context(self, new_state: AgentState):
        """Context manager for handling agent state transitions"""
        previous_state = self.state
        self.state = new_state
        try:
            yield
        finally:
            self.state = previous_state

    def update_memory(self, role: str, content: str, **kwargs) -> None:
        """Update memory with new message"""
        if role == "user":
            msg = Message.user_message(content)
        elif role == "system":
            msg = Message.system_message(content)
        elif role == "assistant":
            msg = Message.assistant_message(content)
        elif role == "tool":
            msg = Message.tool_message(content, **kwargs)
        else:
            raise ValueError(f"Unsupported message role: {role}")

        self.memory.add_message(msg)

    @abstractmethod
    async def run(self, request: Optional[str] = None) -> str:
        """Main execution loop"""
        pass
