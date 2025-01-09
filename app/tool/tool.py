from abc import ABC, abstractmethod
from typing import ClassVar, Optional

from openai.types import FunctionDefinition
from openai.types.chat import ChatCompletionToolParam
from pydantic import BaseModel


class Tool(ABC, BaseModel):
    name: ClassVar[str]
    description: ClassVar[str]
    parameters: ClassVar[Optional[dict]] = None

    class Config:
        arbitrary_types_allowed = True

    @abstractmethod
    async def execute(self, **kwargs):
        """Execute the tool with given parameters."""

    @classmethod
    def to_tool_param(cls) -> ChatCompletionToolParam:
        """Convert tool to Claude function call format."""
        return ChatCompletionToolParam(
            type="function",
            function=FunctionDefinition(
                name=cls.name,
                description=cls.description,
                parameters=cls.parameters,
            ),
        )
