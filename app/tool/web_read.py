from typing import Literal, Optional
from urllib.parse import urljoin

import html2text
from pydantic import model_validator

from app.tool.base import BaseTool
from app.tool.browser import Browser, BrowserResult


WEB_READ_DESCRIPTION = """Read (convert to markdown) content from a webpage. You should prefer using the `webpage_read` tool over the `browser` tool, but do use the `browser` tool if you need to interact with a webpage (e.g., click a button, fill out a form, etc.).
You may use the `webpage_read` tool to read content from a webpage, and even search the webpage content using a Google search query (e.g., url=`https://www.google.com/search?q=YOUR_QUERY`).
"""


class WebRead(BaseTool):
    """Tool for reading and converting webpage content to markdown"""

    name: str = "web_read"
    description: str = WEB_READ_DESCRIPTION
    parameters: dict = {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "The URL of the webpage to read. You can also use a Google search query here (e.g., `https://www.google.com/search?q=YOUR_QUERY`).",
            }
        },
        "required": ["url"],
    }

    browser: Optional[Browser] = None
    html_converter: Optional[html2text.HTML2Text] = None
    trigger_by_action: Literal["browse"] = "browse"

    @model_validator(mode="after")
    def initialize(self):
        """Initialize browser and HTML converter with optimal settings"""
        if not self.browser:
            self.browser = Browser()
            self.html_converter = html2text.HTML2Text()
            self.html_converter.ignore_links = False
            self.html_converter.ignore_images = True
            self.html_converter.images_to_alt = True
            self.html_converter.body_width = 0
        return self

    async def execute(self, url: str, wait_time: int = 1000) -> BrowserResult:
        """Read and convert webpage content to markdown format"""
        try:
            # Normalize URL
            normalized_url = (
                urljoin("https://", url)
                if not url.startswith(("http://", "https://", "file://"))
                else url
            )

            # Execute browser navigation
            result = await self.browser.execute(
                f'goto("{normalized_url}")\nnoop({wait_time})'
            )

            return result

        except Exception as e:
            return BrowserResult(error=f"Failed to read webpage: {str(e)}", url=url)

    def close(self):
        """Close the browser tool."""
        if self.browser is not None:
            self.browser.close()


async def main():
    tool = WebRead()
    result = await tool.execute("https://example.com")
    print(result)


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
