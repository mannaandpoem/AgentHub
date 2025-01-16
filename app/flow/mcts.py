from app.agent.base import BaseAgent
from app.flow.base import BaseFlow
from app.tool import ToolCollection


class MCTSFlow(BaseFlow):
    """Monte Carlo Tree Search based execution flow"""

    def __init__(
        self, agent: BaseAgent, tools: ToolCollection, num_simulations: int = 5
    ):
        super().__init__(agent, tools)
        self.num_simulations = num_simulations

    async def execute(self, input_text: str) -> str:
        pass
