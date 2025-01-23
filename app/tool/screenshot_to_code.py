from typing import Literal, Optional
from urllib.parse import urlparse

from pydantic import field_validator

from app.llm import LLM
from app.prompt.snap_coder import REACT_TAILWIND_SYSTEM_PROMPT
from app.tool import BaseTool
from app.tool.base import ToolResult
from app.utils.extract_html_content import extract_html_content
from app.tool.screenshot import ScreenshotTool


class ScreenshotToCodeTool(BaseTool):
    name: str = "screenshot_to_code"
    description: str = "Generates React/Tailwind code from a URL or local image"
    parameters: dict = {
        "type": "object",
        "properties": {
            "source": {
                "type": "string",
                "description": "URL or local image path"
            },
            "stack": {
                "type": "string",
                "enum": ["react-tailwind"],
                "default": "react-tailwind",
                "description": "Technology stack to generate code for"
            },
            "generation_type": {
                "type": "string",
                "enum": ["create", "update"],
                "default": "create",
                "description": "Whether to create new code or update existing code"
            },
            "device": {
                "type": "string",
                "enum": ["desktop", "mobile"],
                "default": "desktop",
                "description": "Device type for screenshot capture"
            }
        },
        "required": ["source"]
    }

    llm: LLM = LLM()
    screenshot_key: Optional[str] = None
    screenshot_tool: ScreenshotTool = ScreenshotTool(screenshot_key=screenshot_key)

    @field_validator('screenshot_key')
    @classmethod
    def update_screenshot_tool(cls, value: Optional[str], info) -> Optional[str]:
        instance = info.context.get('self')
        if instance and value is not None:
            instance.screenshot_tool.screenshot_key = value
        return value

    async def execute(
            self,
            source: str,
            stack: str = "react-tailwind",
            generation_type: Literal["create", "update"] = "create",
            device: str = "desktop"
    ) -> ToolResult:
        try:
            # Get screenshot or load image
            screenshot_result = await self.screenshot_tool.execute(
                source=source,
                device=device
            )

            if screenshot_result.error:
                return ToolResult(error=f"Failed to get image: {screenshot_result.error}")

            # Get base64 image data from screenshot result
            image_data = screenshot_result.system

            # Create prompt messages
            prompt_messages = [
                {
                    "role": "system",
                    "content": REACT_TAILWIND_SYSTEM_PROMPT
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "image_url": image_data
                        }
                    ]
                }
            ]

            # Generate code using LLM
            rsp = await self.llm.ask(prompt_messages)

            # Extract HTML content
            html_content = extract_html_content(rsp)

            return ToolResult(
                output=f"Successfully generated code from {'URL' if urlparse(source).scheme else 'local image'}",
                system=html_content
            )

        except Exception as e:
            return ToolResult(
                error=f"Code generation failed: {str(e)}"
            )


async def main():
    # Initialize tool
    tool = ScreenshotToCodeTool()

    # Generate code from local image
    result = await tool.execute(
        source="/Users/manna/PycharmProjects/AgentHub/img.png",
    )

    if result.error:
        print(f"Error: {result.error}")
    else:
        print(f"Success: {result.output}")
        print(f"Generated HTML: {result.system}")

    # Save generated code to file
    with open("generated_code.html", "w") as f:
        f.write(result.system)


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
