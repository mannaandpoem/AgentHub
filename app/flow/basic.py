from app.flow.base import BaseFlow
from app.logger import logger


class BasicFlow(BaseFlow):
    """Simple sequential execution flow"""

    async def execute(self, input_text: str) -> str:
        try:
            result = await self.agent.run(input_text)
            return result
        except Exception as e:
            logger.error(f"Error in BasicFlow: {str(e)}")
            return f"Execution failed: {str(e)}"
