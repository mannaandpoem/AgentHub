import asyncio
from typing import List
from app.llm import LLM
from app.schema import Message, Memory
from app.tool.base import FixedTool, BaseTool
from app.logger import logger
from app.agent.toolcall import ToolCallAgent


DESCRIPTION = "Manage conversation memory by maintaining recent messages and summarizing old ones"

SYSTEM = """You are a memory manager that helps summarize conversation history. Your task is to analyze the conversation and create a concise summary focusing on:

1. Key Actions & Decisions:
   - Important actions taken or decisions made
   - Significant choices and their outcomes
   - Tasks completed or in progress

2. Critical Insights:
   - Main discoveries or realizations
   - Important patterns or trends identified
   - Key learnings and understanding gained

3. Essential Context:
   - Relevant background information
   - Important preferences or constraints mentioned
   - Established goals or objectives

Please create a clear, structured summary that preserves these critical elements while omitting routine exchanges and redundant information. Focus on information that would be most valuable for continuing the conversation effectively.

Format your summary as:
[Actions & Decisions]
- Key action points...

[Critical Insights]
- Main insights...

[Essential Context]
- Important context...

user: The role that makes the request
assistant: The role that addresses the current requirement
tool: The return content of the tool used by the assistant to execute
"""


class MemoryManager(FixedTool):
    """A tool for managing conversation memory with summarization."""

    name: str = "memory_manager"
    description: str = DESCRIPTION
    parameters: dict = {
        "type": "object",
        "properties": {
            "min_messages": {
                "type": "integer",
                "description": "Minimum number of messages before compression",
            },
            "max_messages": {
                "type": "integer",
                "description": "Maximum number of messages to maintain",
            },
        },
        "required": ["min_messages", "max_messages"],
    }

    # TODO
    #  Get more granular about the chat logs
    async def summarize_messages(self, messages: List[Message]) -> str:
        """Summarize a list of messages into a concise context."""

        llm = LLM(config_name=self.name)

        if not llm:
            raise ValueError("LLM not initialized")

        # Convert messages to text format
        conversation = "\n".join([
            f"{msg.role}: {msg.content}\n"
            f"- {msg.tool_calls}"
            for msg in messages
        ])

        logger.info(conversation)

        conversation_messages = Message.user_message(content=conversation)

        # Get summary from LLM
        summary = await llm.ask(
            messages=[conversation_messages.to_dict()],
            system_msgs=SYSTEM,
            stream=False
        )

        return summary

    async def execute(self, min_messages: int = 30, max_messages: int = 60) -> None:
        """
        Manage memory by keeping recent messages and summarizing old ones.
        Compression triggers only when messages exceed max_messages.
        Compresses messages between min_messages and max_messages range.
        """
        if not self.agent:
            raise ValueError("Failed to get agent state")

        messages = self.agent.memory.messages
        total_messages = len(messages)

        # Only process if messages exceed max limit
        if total_messages <= max_messages:
            logger.info(f"Memory within limits ({total_messages}/{max_messages} messages)")
            return

        # Keep the most recent min_messages intact
        messages_to_keep = messages[-min_messages:]

        # Summarize messages between min and max range
        messages_to_summarize = messages[:-min_messages]

        if messages_to_summarize:
            summary = await self.summarize_messages(messages_to_summarize)
            summary_message = Message.user_message(
                content=f"Previous conversation summary: {summary}"
            )

            # Combine oldest messages (if any), summary, and recent messages
            self.agent.memory.messages = (
                    [summary_message] +  # Summary of mid-range messages
                    messages_to_keep  # Most recent messages
            )

            logger.info(
                f"Memory compressed: {len(messages_to_summarize)} messages summarized, "
                f"maintaining {len(messages_to_keep)} recent messages"
                f"Summary content:{summary}"
            )


async def test_memory_manager():
    # 创建测试用的Agent和Memory
    memory = Memory()
    agent = ToolCallAgent()
    agent.memory = memory

    # 创建MemoryManager实例
    memory_manager = MemoryManager()
    memory_manager.agent = agent  # 设置agent

    # 生成测试消息
    test_messages = []
    for i in range(60):  # 生成60条测试消息
        if i % 2 == 0:
            msg = Message.user_message(content=f"User message {i}")
        else:
            msg = Message.assistant_message(content=f"Assistant reply {i}")
        test_messages.append(msg)

    # 将消息添加到memory中
    agent.memory.messages = test_messages

    print("Initial message count:", len(agent.memory.messages))
    print("\nFirst few messages before compression:")
    for msg in agent.memory.messages[:3]:
        print(f"{msg.role}: {msg.content}")
    print("...")
    for msg in agent.memory.messages[-3:]:
        print(f"{msg.role}: {msg.content}")

    # 执行内存管理
    await memory_manager.execute(min_messages=20, max_messages=50)

    print("\nMessage count after compression:", len(agent.memory.messages))
    print("\nMessages after compression:")
    for msg in agent.memory.messages[:3]:
        print(f"{msg.role}: {msg.content}")
    print("...")
    for msg in agent.memory.messages[-3:]:
        print(f"{msg.role}: {msg.content}")


if __name__ == "__main__":
    asyncio.run(test_memory_manager())