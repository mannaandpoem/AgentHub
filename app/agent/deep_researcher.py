from typing import List

from app.agent.plan_and_solve import PlanAndSolveAgent


class DeepResearcher(PlanAndSolveAgent):
    name: str = "DeepResearcher"

    async def plan(self) -> List[str]:
        pass

    async def solve(self, plan_step: str) -> str:
        pass
