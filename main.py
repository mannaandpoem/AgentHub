import asyncio

from app.agent import ToolCallAgent
from app.logger import logger
from app.tool import Browser, Terminal, WebRead


async def main():
    agent = ToolCallAgent()
    agent.available_tools.add_tools(
        Terminal(),
        Browser(),
        WebRead(),
    )
    while True:
        try:
            prompt = input("Enter your prompt (or 'exit' to quit): ")
            if prompt.lower() == "exit":
                logger.info("Goodbye!")
                break
            logger.warning("Processing your requirement...")
            await agent.run(prompt)
        except KeyboardInterrupt:
            logger.warning("Goodbye!")
            break


if __name__ == "__main__":
    asyncio.run(main())
