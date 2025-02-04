import re
from typing import Union, List
from pydantic import Field

from app.llm import LLM
from app.prompt.prompt_generator import META_PROMPT
from app.tool.base import BaseTool, ToolResult


class PromptGeneratorTool(BaseTool):
    """Tool for automatically generating AI prompt templates with example support."""

    name: str = "prompt_generator"
    description: str = "Generates customized prompt templates for specific tasks, following prompt engineering best practices"
    parameters: dict = {
        "type": "object",
        "properties": {
            "task": {
                "type": "string",
                "description": "Description of the task you want to generate a prompt template for"
            },
            "variables": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional list of variable names to include in the prompt template",
                "default": []
            },
            "model": {
                "type": "string",
                "description": "Name of the model to use for prompt generation",
                "default": "claude-3-5-sonnet-20241022"
            }
        },
        "required": ["task"]
    }

    metaprompt: str = META_PROMPT

    llm: LLM = Field(default_factory=LLM)

    @classmethod
    def validate_variables(cls, v):
        """Convert various variable input formats to a list."""
        if isinstance(v, str):
            if v.strip() == "":
                return []
            # Handle newline-separated variable string
            return [var.strip().strip('${}') for var in v.split('\n') if var.strip()]
        elif isinstance(v, (list, tuple)):
            return list(v)
        raise ValueError("Variables must be a string or list of strings")

    @staticmethod
    def format_variables(variables: List[str]) -> str:
        """Format variables list into the required string format."""
        if not variables:
            return ""
        return "\n".join([f"${{{var}}}" for var in variables])

    async def execute(
            self,
            task: str,
            variables: Union[List[str], str, None] = None
    ) -> ToolResult:
        """
        Execute the prompt generation process.

        Args:
            task: Description of the task to generate a prompt for
            variables: List of variable names or formatted string

        Returns:
            ToolResult containing the generated prompt template
        """
        try:
            # Convert variables to standard format
            validated_vars = self.validate_variables(variables)
            variable_string = self.format_variables(validated_vars)

            # Replace task placeholder in metaprompt
            prompt = self.metaprompt.replace("{{TASK}}", task)

            # Construct assistant partial response
            assistant_partial = "<Inputs>"
            if variable_string:
                assistant_partial += f"{variable_string}\n</Inputs>\n<Instructions Structure>"

            # Create message for the model
            response = await self.llm.ask(
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    },
                    {
                        "role": "assistant",
                        "content": assistant_partial
                    }
                ],
                temperature=0
            )

            # Extract and process the generated prompt
            generated_prompt = self._extract_prompt(response)

            # Extract variables used in the prompt
            used_variables = self._extract_variables(generated_prompt)

            # Check for any variables that were requested but not used
            unused_variables = set(validated_vars) - used_variables

            # Prepare system message
            system_msg = []
            if used_variables:
                system_msg.append(f"Variables used in template: {', '.join(used_variables)}")
            if unused_variables:
                system_msg.append(f"Warning: Requested variables not used: {', '.join(unused_variables)}")

            return ToolResult(
                output=generated_prompt,
                system="\n".join(system_msg) if system_msg else None
            )

        except Exception as e:
            return ToolResult(error=f"Failed to generate prompt template: {str(e)}")

    @staticmethod
    def _extract_between_tags(tag: str, string: str, strip: bool = False) -> list[str]:
        """Extract content between specified XML-style tags."""
        ext_list = re.findall(f"<{tag}>(.+?)</{tag}>", string, re.DOTALL)
        if strip:
            return [e.strip() for e in ext_list]
        return ext_list

    @staticmethod
    def _remove_empty_tags(text: str) -> str:
        """Remove empty XML-style tags from text."""
        return re.sub(r'\n<(\w+)>\s*</\1>\n', '', text, flags=re.DOTALL)

    @staticmethod
    def _strip_last_sentence(text: str) -> str:
        """Remove the last sentence if it starts with 'Let me know'."""
        sentences = text.split('. ')
        if sentences[-1].startswith("Let me know"):
            sentences = sentences[:-1]
            result = '. '.join(sentences)
            if result and not result.endswith('.'):
                result += '.'
            return result
        return text

    def _extract_prompt(self, metaprompt_response: str) -> str:
        """Extract and process the prompt template from the metaprompt response."""
        between_tags = self._extract_between_tags("Instructions", metaprompt_response)[0]
        processed = between_tags[:1000] + self._strip_last_sentence(
            self._remove_empty_tags(
                self._remove_empty_tags(between_tags[1000:]).strip()
            ).strip()
        )
        return processed

    @staticmethod
    def _extract_variables(prompt: str) -> set:
        """Extract variable names from the prompt template."""
        pattern = r'{([^}]+)}'
        return set(re.findall(pattern, prompt))


async def main():
    # Initialize the tool
    prompt_generator = PromptGeneratorTool()

    result = await prompt_generator.execute(
        task="Draft an email responding to a customer complaint",
        variables=["CUSTOMER_COMPLAINT", "COMPANY_NAME"]  # or newline-separated string
    )

    # Access the results
    if result.error:
        print(f"Error: {result.error}")
    else:
        print(f"Generated prompt: {result.output}")
        if result.system:
            print(f"System info: {result.system}")


if __name__ == '__main__':
    import asyncio

    asyncio.run(main())
