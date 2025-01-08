import json
import re


def transform_tool_call_to_command(tool_call):
    """
    Transform OpenAI tool call format to standardized command format.

    Args:
        tool_call: The tool call object from OpenAI API response

    Returns:
        dict: Standardized command format with command_name and args
    """

    args = json.loads(tool_call.function.arguments or "{}")
    tool_name = tool_call.function.name

    return {"command": tool_name, "args": args}


def parse_oh_aci_output(tool_output, return_string=True):
    pattern = r'<oh_aci_output_.*?>(.*?)</oh_aci_output_'
    json_data = json.loads(re.search(pattern, tool_output, re.DOTALL).group(1).strip())
    return json_data["formatted_output_and_error"] if return_string else json_data
