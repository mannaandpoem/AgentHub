from abc import ABC, abstractmethod
from typing import Any, List, Optional

from pydantic import Field

from app.agent.base import BaseAgent
from app.llm import LLM
from app.schema import AgentState, Memory


class ReActAgent(BaseAgent, ABC):
    name: str
    description: Optional[str] = None

    system_prompt: Optional[str] = None
    next_step_prompt: Optional[str] = None

    llm: Optional[LLM] = Field(default_factory=LLM)
    memory: Memory = Field(default_factory=Memory)
    state: AgentState = AgentState.IDLE

    max_steps: int = 10
    current_step: int = 0

    @abstractmethod
    async def think(self) -> bool:
        """Process current state and decide next action"""

    @abstractmethod
    async def act(self) -> str:
        """Execute decided actions"""

    async def run(self, request: Optional[str] = None) -> str:
        """Main execution loop"""
        if request:
            self.update_memory("user", request)

        results = []
        async with self.state_context(AgentState.RUNNING):
            while self.current_step < self.max_steps:
                self.current_step += 1

                # Think phase
                should_act = await self.think()
                if not should_act:
                    results.append("Thinking complete - no action needed")
                    break

                # Act phase
                result = await self.act()
                step_result = f"Step {self.current_step}: {result}"
                results.append(step_result)

                if self.state == AgentState.FINISHED:
                    break

            if self.current_step >= self.max_steps:
                results.append(f"Reached maximum steps limit ({self.max_steps})")

        return "\n".join(results)
