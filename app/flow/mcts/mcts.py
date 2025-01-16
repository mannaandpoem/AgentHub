import math
from typing import Optional

from app.agent.base import BaseAgent
from app.flow.base import BaseFlow
from app.flow.mcts.search_tree import (
    BestFirstSelector,
    CompositeEvaluator,
    Expander,
    FallbackEvaluator,
    LLMEvaluator,
    Node,
    SearchTree,
)
from app.llm import LLM
from app.logger import logger
from app.tool import ToolCollection


class MCTSFlow(BaseFlow):
    """Enhanced Monte Carlo Tree Search based execution flow"""

    llm: LLM = LLM()

    def __init__(
        self,
        agent: BaseAgent,
        tools: ToolCollection,
        num_simulations: int = 5,
        max_iterations: int = 10,
        max_depth: Optional[int] = None,
        exploration_constant: float = 1 / math.sqrt(2),
        reward_threshold: Optional[float] = None,
        evaluator_type: Optional[str] = None,
    ):
        super().__init__(agent, tools)
        self.num_simulations = num_simulations
        self.max_iterations = max_iterations
        self.max_depth = max_depth
        self.exploration_constant = exploration_constant
        self.reward_threshold = reward_threshold

        # Set up evaluator
        if evaluator_type == "llm":
            self.evaluator = LLMEvaluator(llm=self.llm)
        elif evaluator_type == "fallback":
            self.evaluator = FallbackEvaluator()
        else:
            self.evaluator = CompositeEvaluator(
                evaluators=[LLMEvaluator(llm=self.llm), FallbackEvaluator()],
                weights=[0.8, 0.2],
            )

        # Initialize components
        self.selector = BestFirstSelector(exploration_constant=exploration_constant)
        self.expander = Expander(max_expansions=1)
        self.search_tree = None

    async def execute(self, input_text: str) -> str:
        """Execute the MCTS-based flow with the given input."""
        best_result = None
        best_score = float("-inf")

        for sim in range(self.num_simulations):
            try:
                logger.info(f"Starting simulation {sim + 1}/{self.num_simulations}")

                # Initialize search tree for this simulation
                self.search_tree = SearchTree(
                    root=Node(node_id=0, message=input_text),
                    agent=self.agent,
                    selector=self.selector,
                    max_iterations=self.max_iterations,
                    max_depth=self.max_depth,
                    reward_threshold=self.reward_threshold,
                )

                # Run the search
                best_node = await self._run_search()

                if best_node:
                    result = best_node.message
                    score = await self._evaluate_result(result)

                    if score > best_score:
                        best_score = score
                        best_result = result

                    logger.info(f"Simulation {sim + 1} completed with score: {score}")

            except Exception as e:
                logger.error(f"Simulation {sim + 1} failed: {str(e)}")
                continue

        return best_result or "All simulations failed"

    async def _run_search(self) -> Optional[Node]:
        """Run the MCTS algorithm for a specified number of iterations."""
        for iteration in range(self.max_iterations):
            try:
                # Selection
                node = self.search_tree.select_node(self.search_tree.root)
                if not node:
                    break

                # Expansion
                new_node = self.search_tree.expand_node(node)

                # Simulation
                reward = await self._simulate(new_node)

                # Backpropagation
                await self._back_propagate(new_node, reward)

                # Check for early termination
                if self.reward_threshold and reward >= self.reward_threshold:
                    break

                logger.info(
                    f"Completed iteration {iteration + 1}/{self.max_iterations}"
                )

            except Exception as e:
                logger.error(f"Error in iteration {iteration + 1}: {str(e)}")
                continue

        return self.search_tree.get_best_node()

    async def _simulate(self, node: Node) -> float:
        """Simulate from the given node and return a reward value."""
        # Use the agent to generate and execute actions
        try:
            result = await self.agent.generate(node.message)
            # Execute any tool calls if needed
            if hasattr(self.agent, "execute_tool_calls"):
                result = await self.agent.execute_tool_calls(result)

            # Calculate reward based on the result
            reward = self._evaluate_result(result)
            node.message = result  # Store the result in the node

            return reward

        except Exception as e:
            logger.error(f"Simulation failed: {str(e)}")
            return 0.0

    @staticmethod
    async def _back_propagate(node: Node, reward: float):
        """Back propagate the reward through the tree."""
        current = node
        while current:
            current.visits += 1
            current.value += reward
            current = current.parent

    async def _evaluate_result(self, result: str) -> float:
        """Evaluate the quality of a result."""
        if not result:
            return 0.0

        evaluation_prompt = [
            {
                "role": "system",
                "content": (
                    "You are an expert evaluator of AI agent responses. "
                    "Rate the response quality on a scale of 0.0 to 1.0 based on these criteria:\n"
                    "- Relevance and accuracy (0.4 weight)\n"
                    "- Completeness and detail (0.3 weight)\n"
                    "- Clarity and coherence (0.3 weight)\n"
                    "Provide only a number as output, no explanation."
                ),
            },
            {"role": "user", "content": f"Evaluate this response: {result}"},
        ]

        try:
            llm_response = await self.llm.ask(messages=evaluation_prompt)
            # Extract numerical score from response
            try:
                score = float(llm_response.strip())
                return max(0.0, min(1.0, score))  # Ensure score is between 0 and 1
            except ValueError:
                logger.warning(
                    "LLM returned non-numerical score, using fallback evaluation"
                )
                return self._fallback_evaluation(result)

        except Exception as e:
            logger.error(f"LLM evaluation failed: {str(e)}")
            return self._fallback_evaluation(result)

    def _fallback_evaluation(self, result: str) -> float:
        """Fallback evaluation method when LLM evaluation fails."""
        # Basic metrics for fallback scoring
        if not result:
            return 0.0

        # Word count scoring (up to 50 words for max score)
        words = result.split()
        word_score = min(len(words) / 50.0, 1.0) * 0.4

        # Sentence structure scoring
        sentences = [s.strip() for s in result.split(".") if s.strip()]
        sentence_score = min(len(sentences) / 3.0, 1.0) * 0.3

        # Complexity scoring (average word length as a simple proxy)
        avg_word_length = sum(len(word) for word in words) / (len(words) or 1)
        complexity_score = min(avg_word_length / 8.0, 1.0) * 0.3

        return word_score + sentence_score + complexity_score

    def _generate_unique_id(self) -> int:
        """Generate a unique ID for new nodes."""
        if not hasattr(self, "_next_id"):
            self._next_id = 0
        self._next_id += 1
        return self._next_id
