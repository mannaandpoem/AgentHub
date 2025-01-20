from abc import abstractmethod
from typing import Optional, List

from pydantic import Field

from app.agent.base import BaseAgent
from app.schema import AgentState


class PlanAndSolveAgent(BaseAgent):
    """
    Plan-and-Solve Agent that breaks down problems into planning and solution phases.
    Based on the "Plan-and-Solve Prompting" paper approach.
    """
    name: str = "PlanAndSolve"
    description: str = "Agent that uses plan-and-solve prompting to break down and solve problems"

    # Additional fields specific to Plan-and-Solve
    planning_prompt: Optional[str] = None
    solution_prompt: Optional[str] = None

    current_plan: List[str] = Field(default_factory=list)

    max_steps: int = 10
    current_step: int = 0

    @abstractmethod
    async def plan(self) -> List[str]:
        """
        Generate a plan of steps to solve the problem.
        Returns a list of planned steps.
        """
        pass

    @abstractmethod
    async def solve(self, plan_step: str) -> str:
        """
        Execute a single step from the plan.
        Returns the solution/result for that step.
        """
        pass

    async def run(self, request: Optional[str] = None) -> str:
        """
        Main execution loop following the Plan-and-Solve approach:
        1. Planning Phase: Break down the problem into steps
        2. Solution Phase: Execute each step of the plan
        """
        if request:
            self.update_memory("user", request)

        results = []
        async with self.state_context(AgentState.RUNNING):
            # Planning Phase
            self.current_plan = await self.plan()
            results.append(f"Plan created with {len(self.current_plan)} steps:")
            for i, step in enumerate(self.current_plan, 1):
                results.append(f"  {i}. {step}")

            # Solution Phase
            for step_num, plan_step in enumerate(self.current_plan, 1):
                self.current_step = step_num

                if self.current_step > self.max_steps:
                    results.append(f"Reached maximum steps limit ({self.max_steps})")
                    break

                # Execute the planned step
                solution = await self.solve(plan_step)
                results.append(f"\nStep {step_num}: {plan_step}")
                results.append(f"Solution: {solution}")

                if self.state == AgentState.FINISHED:
                    break

        return "\n".join(results)
