from typing import List, Optional

from app.agent.base import BaseAgent
from app.flow.aflow import AFlow
from app.flow.base import BaseFlow, FlowType
from app.flow.basic import BasicFlow
from app.flow.mcts.mcts import MCTSFlow
from app.tool import BaseTool, ToolCollection


class FlowFactory:
    """Factory for creating different types of flows"""

    @staticmethod
    def create_flow(
        flow_type: FlowType,
        agent: BaseAgent,
        tools: Optional[ToolCollection] = None,
        **kwargs,
    ) -> BaseFlow:
        flows = {
            FlowType.BASIC: BasicFlow,
            FlowType.MCTS: MCTSFlow,
            FlowType.AFLOW: AFlow,
        }

        flow_class = flows.get(flow_type)
        if not flow_class:
            raise ValueError(f"Unknown flow type: {flow_type}")

        return flow_class(agent, tools, **kwargs)


async def loop(
    agent: BaseAgent,
    tools: Optional[List[BaseTool]] = None,
    flow_type: FlowType = FlowType.BASIC,
    input_text: str = "",
    **loop_kwargs,
) -> str:
    """Main entry point for running an agent with specified flow type"""
    tool_collection = ToolCollection(*tools) if tools else None
    flow = FlowFactory.create_flow(flow_type, agent, tool_collection, **loop_kwargs)
    return await flow.execute(input_text)
