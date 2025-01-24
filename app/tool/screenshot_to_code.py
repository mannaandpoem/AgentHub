from typing import Optional
from urllib.parse import urlparse

from app.llm import LLM
from app.prompt.screenshot_to_code import SYSTEM_PROMPTS, USER_PROMPTS
from app.tool import BaseTool
from app.tool.base import ToolResult
from app.tool.oh_editor import OHEditor
from app.utils.extract_html_content import extract_code_content
from app.tool.screenshot import ScreenshotTool


class ScreenshotToCodeTool(BaseTool):
    name: str = "screenshot_to_code"
    description: str = "Generates frontend code from a URL or local image using various tech stacks"
    parameters: dict = {
        "type": "object",
        "properties": {
            "source": {
                "type": "string",
                "description": "URL or local image path"
            },
            "device": {
                "type": "string",
                "enum": ["desktop", "mobile"],
                "default": "desktop",
                "description": "Device type for screenshot capture"
            },
            "target_path": {
                "type": "string",
                "description": "File path to save the generated code"
            },
            "stack": {
                "type": "string",
                "enum": ["react-tailwind", "html-tailwind", "svg"],
                "default": "react-tailwind",
                "description": "Target technology stack for frontend code generation"
            }
        },
        "required": ["source", "target_path"]
    }

    llm: LLM = LLM("vision")
    screenshot_tool: ScreenshotTool = ScreenshotTool()
    editor: OHEditor = OHEditor()

    @staticmethod
    def create_prompt_messages(
            image_data: str,
            stack: str,
            result_image: Optional[str] = None
    ) -> list:
        system_content = SYSTEM_PROMPTS[stack]
        user_prompt = USER_PROMPTS[stack]

        user_content: list = [
            {
                "type": "image_url",
                "image_url": {"url": image_data, "detail": "high"}
            },
            {
                "type": "text",
                "text": user_prompt
            }
        ]

        if result_image:
            user_content.insert(
                1,
                {
                    "type": "image_url",
                    "image_url": {"url": result_image, "detail": "high"}
                }
            )

        return [
            {
                "role": "system",
                "content": system_content
            },
            {
                "role": "user",
                "content": user_content
            }
        ]

    async def execute(
            self,
            source: str,
            target_path: str,
            device: str = "desktop",
            stack: str = "react-tailwind"
    ) -> ToolResult:
        try:
            # Get screenshot or load image
            screenshot_result = await self.screenshot_tool.execute(
                source=source,
                device=device
            )

            if screenshot_result.error:
                return ToolResult(error=f"Failed to get image: {screenshot_result.error}")

            # Create prompt messages
            prompt_messages = self.create_prompt_messages(
                image_data=screenshot_result.system,
                stack=stack
            )

            # Generate code using LLM
            response = await self.llm.ask(prompt_messages)

            # Extract code content
            code_content = extract_code_content(response, stack)

            # Save generated code
            await self.editor.execute(
                command="create",
                path=target_path,
                file_text=code_content
            )

            # View the generated code
            view_result = await self.editor.execute(
                command="view",
                path=target_path
            )

            return ToolResult(
                output=f"Successfully generated code from {'URL' if urlparse(source).scheme else 'local image'} to {target_path}.\n{str(view_result)}",
            )

        except Exception as e:
            return ToolResult(
                error=f"Code generation failed: {str(e)}"
            )
