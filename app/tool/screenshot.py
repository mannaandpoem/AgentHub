from typing import Optional

from pydantic import field_validator

from app.tool import BaseTool
from app.tool.base import ToolResult

import base64
import os
import httpx
from urllib.parse import urlparse


class ScreenshotTool(BaseTool):
    name: str = "screenshot"
    description: str = "Loads an image from local path or captures screenshot from URL"
    parameters: dict = {
        "type": "object",
        "properties": {
            "source": {
                "type": "string",
                "description": "Local image path or URL to capture"
            },
            "device": {
                "type": "string",
                "enum": ["desktop", "mobile"],
                "default": "desktop",
                "description": "Device type to emulate for URL screenshots"
            },
            "mime_type": {
                "type": "string",
                "default": "image/png",
                "description": "MIME type for local images"
            }
        },
        "required": ["source"]
    }
    screenshot_key: Optional[str] = None

    async def execute(
            self,
            source: str,
            device: str = "desktop",
            mime_type: str = "image/png"
    ) -> ToolResult:
        try:
            # Determine if source is URL or file path
            is_url = bool(urlparse(source).scheme)

            if is_url:
                if not self.screenshot_key:
                    return ToolResult(
                        error="API key is required for URL screenshots. Please provide 'screenshot_key' parameter."
                    )
                return await self._handle_url(source, self.screenshot_key, device)
            else:
                return await self._handle_local_file(source, mime_type)

        except Exception as e:
            return ToolResult(error=f"Screenshot operation failed: {str(e)}")

    async def _handle_local_file(self, image_path: str, mime_type: str) -> ToolResult:
        """Handle local image file loading"""
        # Validate file exists
        if not os.path.exists(image_path):
            return ToolResult(error=f"Image file not found: {image_path}")

        # Validate file is an image
        valid_extensions = ['.png', '.jpg', '.jpeg', '.gif', '.webp']
        if not any(image_path.lower().endswith(ext) for ext in valid_extensions):
            return ToolResult(
                error=f"Invalid image file type. Supported types: {', '.join(valid_extensions)}"
            )

        # Read image file
        with open(image_path, 'rb') as f:
            image_bytes = f.read()

        # Convert to base64 data URL
        base64_image = self._bytes_to_data_url(image_bytes, mime_type)

        return ToolResult(
            output=f"Successfully loaded image from {image_path}",
            system=base64_image
        )

    async def _handle_url(self, url: str, screenshot_key: str, device: str) -> ToolResult:
        """Handle URL screenshot capture"""
        try:
            image_bytes = await self._capture_screenshot(url, screenshot_key, device)
            base64_image = self._bytes_to_data_url(image_bytes, "image/png")

            return ToolResult(
                output=f"Successfully captured screenshot from {url}",
                system=base64_image
            )
        except Exception as e:
            return ToolResult(error=f"Failed to capture screenshot: {str(e)}")

    async def _capture_screenshot(self, target_url: str, screenshot_key: str, device: str) -> bytes:
        """Capture screenshot using screenshotone.com API"""
        api_base_url = "https://api.screenshotone.com/take"

        params = {
            "access_key": screenshot_key,
            "url": target_url,
            "full_page": "true",
            "device_scale_factor": "1",
            "format": "png",
            "block_ads": "true",
            "block_cookie_banners": "true",
            "block_trackers": "true",
            "cache": "false",
            "viewport_width": "342" if device == "mobile" else "1280",
            "viewport_height": "684" if device == "mobile" else "832"
        }

        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.get(api_base_url, params=params)
            if response.status_code == 200 and response.content:
                return response.content
            else:
                raise Exception(f"API returned status code: {response.status_code}")

    def _bytes_to_data_url(self, image_bytes: bytes, mime_type: str) -> str:
        """Convert image bytes to base64 data URL"""
        base64_image = base64.b64encode(image_bytes).decode("utf-8")
        return f"data:{mime_type};base64,{base64_image}"

    def _get_mime_type(self, file_path: str) -> str:
        """Determine MIME type from file extension"""
        extension = os.path.splitext(file_path)[1].lower()
        mime_types = {
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.gif': 'image/gif',
            '.webp': 'image/webp'
        }
        return mime_types.get(extension, 'image/png')


async def main():
    # Create the tool
    screenshot_key = "..."
    screenshot_tool = ScreenshotTool(screenshot_key=screenshot_key)
    # Local image example
    local_result = await screenshot_tool.execute(
        source="/Users/manna/PycharmProjects/AgentHub/img.png"
    )

    # URL screenshot example
    url_result = await screenshot_tool.execute(
        source="https://example.com",
        device="desktop"
    )

    # Handle results
    for result in [local_result, url_result]:
        if result.error:
            print(f"Error: {result.error}")
        else:
            print(result.output)
            print(f"Image data URL: {result.system[:100]}...")


if __name__ == '__main__':
    import asyncio

    asyncio.run(main())
