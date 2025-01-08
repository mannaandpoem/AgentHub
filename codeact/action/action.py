from pydantic import BaseModel, Field
from typing import Optional, List

from codeact.llm import LLM


class Action(BaseModel):
    name: str = Field(default="")
    context: Optional[dict] = None
    llm: Optional[LLM] = Field(default_factory=LLM)
    prefix: str = Field(default="")
    profile: str = Field(default="")
    desc: str = Field(default="")

    def set_prefix(self, prefix: str, profile: str):
        """Set prefix for later usage"""
        self.prefix = prefix
        self.profile = profile

    def __str__(self):
        return self.__class__.__name__

    def __repr__(self):
        return self.__str__()

    async def _aask(self, prompt: str, system_msgs: Optional[List[str]] = None) -> str:
        """Append default prefix"""
        if not system_msgs:
            system_msgs = []
        system_msgs.append(self.prefix)
        return await self.llm.aask(prompt, system_msgs)

    async def run(self, *args, **kwargs):
        """Run action"""
        raise NotImplementedError("The run method should be implemented in a subclass.")


