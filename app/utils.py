import json
import re


def parse_oh_aci_output(tool_output, return_string=True):
    pattern = r"<oh_aci_output_.*?>(.*?)</oh_aci_output_"
    json_data = json.loads(re.search(pattern, tool_output, re.DOTALL).group(1).strip())
    return json_data["formatted_output_and_error"] if return_string else json_data
