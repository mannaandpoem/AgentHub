import asyncio

from app.agent import CodeActAgent
from app.logger import logger
from app.tool.create_web_template import CreateWebTemplate
from app.tool.deploy_web_project import DeployWebProject


async def main():
    agent = CodeActAgent()
    agent.available_tools.add_tools(
        CreateWebTemplate(),
        DeployWebProject(),
    )
    while True:
        try:
            prompt = input("Enter your prompt (or 'exit' to quit): ")
            if prompt.lower() == "exit":
                logger.info("Goodbye!")
                break
            logger.warning("Processing your request...")
            await agent.run(prompt)
        except KeyboardInterrupt:
            logger.warning("Goodbye!")
            break


if __name__ == "__main__":
    asyncio.run(main())
