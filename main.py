import asyncio

from app.agent.codeact import ToolCallAgent
from app.logger import logger


async def main():
    agent = ToolCallAgent()
    while True:
        try:
            prompt = input("\nEnter your prompt (or 'exit' to quit): ")
            if prompt.lower() == "exit":
                logger.info("Goodbye!")
                break
            logger.warning("\nProcessing your request...\n")
            await agent.run(prompt)
        except KeyboardInterrupt:
            logger.warning("\nGoodbye!")
            break


if __name__ == "__main__":
    asyncio.run(main())
