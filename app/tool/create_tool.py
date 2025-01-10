from typing import Any, Callable, ClassVar, Dict, Optional

from app.tool.tool import Tool


class CreateTool(Tool):
    name: ClassVar[str] = "create_tool"
    description: ClassVar[
        str
    ] = """
    Creates a new tool or function with specified parameters.
    This tool allows dynamic creation of new tools with custom name, description, parameters, and execution logic.
    """
    parameters: ClassVar[dict] = {
        "type": "object",
        "properties": {
            "tool_name": {
                "type": "string",
                "description": "Name of the tool to create",
            },
            "tool_description": {
                "type": "string",
                "description": "Description of what the tool does",
            },
            "tool_parameters": {
                "type": "object",
                "description": "JSON schema for the tool's parameters",
            },
            "execution_code": {
                "type": "string",
                "description": "Python code that defines the execution logic",
            },
        },
        "required": [
            "tool_name",
            "tool_description",
            "tool_parameters",
            "execution_code",
        ],
    }

    # 使用类变量存储创建的工具
    _created_tools: ClassVar[Dict[str, Any]] = {}

    async def execute(
        self,
        tool_name: str,
        tool_description: str,
        tool_parameters: dict,
        execution_code: str,
    ) -> str:
        """
        Creates a new tool dynamically with the specified parameters.
        """
        try:
            # Create the execute function
            namespace = {}
            exec(
                f"async def dynamic_execute(self, **kwargs):\n{execution_code}",
                namespace,
            )

            # Create the tool class dynamically
            tool_class = type(
                tool_name,
                (Tool,),
                {
                    "name": tool_name,
                    "description": tool_description,
                    "parameters": tool_parameters,
                    "execute": namespace["dynamic_execute"],
                },
            )

            # Store the created tool
            CreateTool._created_tools[tool_name] = tool_class

            return f"Successfully created tool: {tool_name}"

        except Exception as e:
            return f"Failed to create tool: {str(e)}"

    @classmethod
    def get_created_tool(cls, tool_name: str) -> Optional[Tool]:
        """
        Retrieves a previously created tool by name.
        """
        return cls._created_tools.get(tool_name)


# Example usage
async def main():
    # Initialize the CreateTool
    creator = CreateTool()

    # Example: Create a calculator tool
    calc_params = {
        "type": "object",
        "properties": {
            "x": {"type": "number"},
            "y": {"type": "number"},
            "operation": {"type": "string", "enum": ["+", "-", "*", "/"]},
        },
        "required": ["x", "y", "operation"],
    }

    calc_code = """
    if kwargs['operation'] == '+':
        return kwargs['x'] + kwargs['y']
    elif kwargs['operation'] == '-':
        return kwargs['x'] - kwargs['y']
    elif kwargs['operation'] == '*':
        return kwargs['x'] * kwargs['y']
    elif kwargs['operation'] == '/':
        return kwargs['x'] / kwargs['y']
    """

    # Create the calculator tool
    result = await creator.execute(
        tool_name="Calculator",
        tool_description="A simple calculator tool that performs basic arithmetic operations",
        tool_parameters=calc_params,
        execution_code=calc_code,
    )
    print(result)

    # Use the created tool
    calc_tool = creator.get_created_tool("Calculator")
    if calc_tool and isinstance(calc_tool, Callable):
        calc_instance = calc_tool()
        result = await calc_instance.execute(x=10, y=5, operation="+")
        print(f"Calculator result: {result}")


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
