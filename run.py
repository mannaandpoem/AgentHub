#!/usr/bin/env python3
"""
CLI entry point for AgentHub
Usage: python run.py --agent-type <agent_type> --tools [tool1,tool2] --input "your input text"
"""

import argparse
import asyncio
from typing import List, Optional, Type

from app.agent import *
from app.flow.base import FlowType
from app.loop import loop
from app.tool import *


def get_tool_class(tool_name: str) -> Type[BaseTool]:
    """Get tool class by name"""
    # Create a mapping of tool names to tool classes
    tool_classes = {
        "bash": Bash,
        "code_review": CodeReview,
        "file_localizer": FileLocalizer,
        "create_tool": CreateTool,
        "file_navigator": FileNavigator,
        "filemap": Filemap,
        "finish": Finish,
        "terminate": Terminate,
        "list_files": ListFiles,
        "search_file": SearchFile,
        "str_replace_editor": StrReplaceEditor,
        "terminal": Terminal,
        "python_execute": PythonExecute,
        "create_chat_completion": CreateChatCompletion,
        "attempt_completion_client_request": AttemptCompletion,
    }

    tool_class = tool_classes.get(tool_name.lower())
    if not tool_class:
        raise ValueError(
            f"Unknown tool: {tool_name}. Available tools: {list(tool_classes.keys())}"
        )

    return tool_class


def create_tools(tools_str: str) -> Optional[List[BaseTool]]:
    """Create list of tool instances from comma-separated tool names"""
    if not tools_str:
        return None

    tool_names = [name.strip() for name in tools_str.split(",")]
    tools = []

    for tool_name in tool_names:
        tool_class = get_tool_class(tool_name)
        tools.append(tool_class())

    return tools


def get_agent(agent_type: str):
    """Factory function to create agent based on type"""
    agent_types = {
        "toolcall": ToolCallAgent,
        "codeact": CodeActAgent,
        "midwit": MidwitAgent,
        "swe": SWEAgent,
        "tao": TaoAgent,
    }

    if agent_type not in agent_types:
        raise ValueError(
            f"Unknown agent type: {agent_type}. Available types: {list(agent_types.keys())}"
        )

    return agent_types[agent_type]()


async def main(args):
    """Main async function to run the agent flow"""
    try:
        agent = get_agent(args.agent_type)
        tools = create_tools(args.tools)

        result = await loop(
            agent=agent,
            tools=tools,
            flow_type=FlowType[args.flow_type.upper()],
            input_text=args.input,
        )
        print(result)

    except Exception as e:
        print(f"Error: {str(e)}")
        raise


def setup_argparse():
    """Setup command line argument parsing"""
    parser = argparse.ArgumentParser(
        description="Run AgentHub with specified configuration"
    )

    parser.add_argument(
        "--agent-type",
        type=str,
        default="toolcall",
        choices=["toolcall", "codeact", "midwit", "swe", "tao"],
        help="Type of agent to use (default: toolcall)",
    )

    parser.add_argument(
        "--tools",
        type=str,
        help='Comma-separated list of tools to use (e.g., "execute_command, terminate")',
    )

    parser.add_argument(
        "--flow-type",
        type=str,
        default="basic",
        choices=["basic", "mcts", "aflow"],
        help="Type of flow to use (default: basic)",
    )

    parser.add_argument(
        "--input", type=str, required=True, help="Input text for the agent to process"
    )

    return parser


if __name__ == "__main__":
    parser = setup_argparse()
    asyncio.run(main(parser.parse_args()))
