import math
import random
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field

from app.agent import ToolCallAgent
from app.logger import logger


class Node(BaseModel):
    """A Node in the MCTS search tree."""

    node_id: int
    message: Optional[str] = None
    reward: Optional[float] = None
    parent: Optional["Node"] = None
    children: List["Node"] = []
    max_expansions: int = 1
    action_steps: List[str] = []
    visits: int = 0
    value: float = 0.0

    def is_finished(self) -> bool:
        """Check if the node is finished based on its reward."""
        return self.reward is not None

    def is_leaf(self) -> bool:
        """Check if the node is a leaf (no children)."""
        return len(self.children) == 0

    def get_all_nodes(self) -> List["Node"]:
        """Get all nodes in the tree."""
        all_nodes = [self]
        for child in self.children:
            all_nodes.extend(child.get_all_nodes())
        return all_nodes

    def get_depth(self) -> int:
        """Return the depth of the node in the tree."""
        depth = 0
        node = self
        while node.parent:
            node = node.parent
            depth += 1
        return depth

    def add_child(self, child_node: "Node"):
        """Add a child to this node."""
        self.children.append(child_node)
        child_node.parent = self


class Selector(ABC, BaseModel):
    @abstractmethod
    def select(self, nodes: List["Node"]) -> Optional["Node"]:
        pass


class BestFirstSelector(Selector):
    """Selects nodes using UCB1 formula for balancing exploration and exploitation."""

    exploration_constant: float = Field(
        1 / math.sqrt(2), description="Exploration constant for UCB1"
    )

    def select(self, nodes: List["Node"]) -> Optional["Node"]:
        if not nodes:
            return None

        parent_visits = sum(node.visits for node in nodes)

        def ucb1_score(node: "Node") -> float:
            exploitation = node.value / (node.visits + 1e-6)
            exploration = math.sqrt(math.log(parent_visits + 1) / (node.visits + 1e-6))
            return exploitation + self.exploration_constant * exploration

        return max(nodes, key=ucb1_score)


class SoftmaxSelector(Selector):
    """Selects nodes using softmax probability distribution based on node values."""

    temperature: float = Field(1.0, description="Temperature parameter for softmax")

    def select(self, nodes: List["Node"]) -> Optional["Node"]:
        if not nodes:
            return None

        values = [node.value for node in nodes]
        max_value = max(values)
        exp_values = [math.exp((v - max_value) / self.temperature) for v in values]
        total = sum(exp_values)
        probs = [v / total for v in exp_values]

        r = random.random()
        cum_prob = 0.0
        for node, prob in zip(nodes, probs):
            cum_prob += prob
            if r <= cum_prob:
                return node
        return nodes[-1]


class Expander:
    """Handles node expansion in the MCTS tree."""

    def __init__(self, max_expansions: int = 1):
        self.max_expansions = max_expansions

    def expand(self, node: "Node", tree: "SearchTree") -> "Node":
        """Expand a node by generating possible actions and creating child nodes."""
        if node.is_finished() or len(node.children) >= self.max_expansions:
            return node

        # Generate possible actions using the agent
        actions = tree.agent.generate_actions(node.message)

        # Create a new child node
        child_node = Node(
            node_id=tree._generate_unique_id(),
            message=f"Action from Node {node.node_id}",
            max_expansions=node.max_expansions,
        )

        # Add the action steps to the child node
        child_node.action_steps = actions

        # Add the child to the parent
        node.add_child(child_node)

        return child_node


class BaseEvaluator(ABC, BaseModel):
    """Base class for response evaluators."""

    @abstractmethod
    async def evaluate(self, result: str) -> float:
        """Evaluate the result and return a score between 0 and 1."""


class FallbackEvaluator(BaseEvaluator):
    """Simple heuristic-based evaluator for fallback scenarios."""

    word_weight: float = Field(0.4, description="Weight for word count scoring")
    sentence_weight: float = Field(
        0.3, description="Weight for sentence structure scoring"
    )
    complexity_weight: float = Field(0.3, description="Weight for complexity scoring")

    max_words: int = Field(50, description="Number of words for maximum word score")
    max_sentences: int = Field(
        3, description="Number of sentences for maximum sentence score"
    )
    ideal_word_length: float = Field(
        8.0, description="Ideal average word length for complexity"
    )

    async def evaluate(self, result: str) -> float:
        if not result:
            return 0.0

        words = result.split()
        sentences = [s.strip() for s in result.split(".") if s.strip()]

        # Word count scoring
        word_score = min(len(words) / self.max_words, 1.0) * self.word_weight

        # Sentence structure scoring
        sentence_score = (
            min(len(sentences) / self.max_sentences, 1.0) * self.sentence_weight
        )

        # Complexity scoring
        avg_word_length = sum(len(word) for word in words) / (len(words) or 1)
        complexity_score = (
            min(avg_word_length / self.ideal_word_length, 1.0) * self.complexity_weight
        )

        return word_score + sentence_score + complexity_score


class LLMEvaluator(BaseEvaluator):
    """LLM-based evaluator using structured prompts."""

    llm: Any = Field(..., description="LLM instance for evaluation")
    fallback: BaseEvaluator = Field(default_factory=FallbackEvaluator)

    system_prompt: str = Field(
        "You are an expert evaluator of AI agent responses. "
        "Rate the response quality on a scale of 0.0 to 1.0 based on these criteria:\n"
        "- Relevance and accuracy (0.4 weight)\n"
        "- Completeness and detail (0.3 weight)\n"
        "- Clarity and coherence (0.3 weight)\n"
        "Provide only a number as output, no explanation."
    )

    class Config:
        arbitrary_types_allowed = True

    async def evaluate(self, result: str) -> float:
        if not result:
            return 0.0

        evaluation_prompt = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": f"Evaluate this response: {result}"},
        ]

        try:
            llm_response = await self.llm.ask(messages=evaluation_prompt)
            try:
                score = float(llm_response.strip())
                return max(0.0, min(1.0, score))
            except ValueError:
                logger.warning(
                    "LLM returned non-numerical score, using fallback evaluation"
                )
                return await self.fallback.evaluate(result)

        except Exception as e:
            logger.error(f"LLM evaluation failed: {str(e)}")
            return await self.fallback.evaluate(result)


class CompositeEvaluator(BaseEvaluator):
    """Combines multiple evaluators with weights."""

    evaluators: List[BaseEvaluator] = Field(..., description="List of evaluators")
    weights: List[float] = Field(..., description="Weights for each evaluator")

    @property
    def total_weight(self) -> float:
        return sum(self.weights)

    async def evaluate(self, result: str) -> float:
        if len(self.evaluators) != len(self.weights):
            raise ValueError("Number of evaluators must match number of weights")

        total_score = 0.0
        for evaluator, weight in zip(self.evaluators, self.weights):
            score = await evaluator.evaluate(result)
            total_score += score * weight

        return total_score / self.total_weight


class SearchTree(BaseModel):
    root: Node = Field(..., description="The root node of the search tree.")
    agent: ToolCallAgent = Field(..., description="Agent for generating actions.")
    evaluator: BaseEvaluator = Field(
        default_factory=FallbackEvaluator, description="Evaluator for response quality"
    )
    selector: Optional[Union[BestFirstSelector, SoftmaxSelector]] = Field(
        default_factory=BestFirstSelector, description="Selector for node selection"
    )

    max_expansions: int = Field(
        1, description="Maximum number of expansions for nodes."
    )
    max_iterations: int = Field(
        10, description="Maximum number of iterations for MCTS."
    )
    max_depth: Optional[int] = Field(None, description="Maximum depth for simulations.")
    reward_threshold: Optional[float] = Field(
        None, description="Reward threshold for early termination."
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata for the search tree."
    )

    def create_search(self, message: str) -> Node:
        """Initialize the search tree with a given message and return the root node."""
        root_node = Node(node_id=0, message=message)
        self.root = root_node
        return root_node

    def select_node(self, node: Node) -> Optional[Node]:
        """Select a node for expansion using UCT (Upper Confidence Bounds for Trees)."""
        expandable_nodes = [child for child in node.children if not child.is_finished()]
        if not expandable_nodes:
            return None

        # Using UCT (Upper Confidence Bounds for Trees) selection method
        return self.selector.select(expandable_nodes)

    def expand_node(self, node: Node) -> Node:
        """Expand the selected node and return a new child node."""
        new_node = Node(
            node_id=node.node_id + 1, message=f"Expanded node {node.node_id}"
        )
        node.add_child(new_node)
        return new_node

    async def simulate(self, node: Node) -> float:
        """Simulate from the current node and return evaluation score."""
        try:
            result = await self.agent.generate(node.message)
            if hasattr(self.agent, "execute_tool_calls"):
                result = await self.agent.execute_tool(result)

            # Use the evaluator to score the result
            score = await self.evaluator.evaluate(result)
            node.message = result

            return score

        except Exception as e:
            logger.error(f"Simulation failed: {str(e)}")
            return 0.0

    @staticmethod
    def back_propagate(node: Node, reward: float):
        """Back propagate the reward up the tree."""
        while node is not None:
            node.visits += 1
            node.value += reward  # Update the node value based on the reward
            node = node.parent

    async def run_search(self) -> Node:
        """Run the MCTS algorithm for a specified number of iterations."""
        for iteration in range(self.max_iterations):
            node = self.select_node(self.root)
            if not node:
                break  # No node to expand

            new_node = self.expand_node(node)
            reward = await self.simulate(new_node)
            self.back_propagate(new_node, float(reward))

        return self.get_best_node()

    def get_best_node(self) -> Optional[Node]:
        """Get the best node based on value (can be adjusted with custom logic)."""
        all_nodes = self.root.get_all_nodes()
        return max(all_nodes, key=lambda n: n.value, default=None)

    def is_finished(self) -> bool:
        """Check if the search should stop (e.g., based on iteration or reward threshold)."""
        if (
            self.max_iterations
            and len(self.root.get_all_nodes()) >= self.max_iterations
        ):
            return True
        if self.reward_threshold and any(
            n.reward >= self.reward_threshold for n in self.root.get_all_nodes()
        ):
            return True
        return False
