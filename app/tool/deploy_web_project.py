import asyncio

from pydantic import BaseModel

from app.tool import BaseTool, Bash
import os
from typing import Optional


class DeployResult(BaseModel):
    success: bool
    message: str
    url: Optional[str] = None


class DeployWebProject(BaseTool):
    name: str = "deploy_web_project"
    description: str = "Launch a Node.js web project's development server using npm scripts"
    parameters: dict = {
        "type": "object",
        "properties": {
            "project_path": {
                "type": "string",
                "description": "Absolute path to Node.js project directory containing package.json",
                "examples": ["/path/to/my-react-app"]
            },
            "port": {
                "type": "integer",
                "description": "Preferred port for development server (default: 5173)",
                "default": 5173
            }
        },
        "required": ["project_path"]
    }

    async def execute(self, **kwargs) -> dict:
        """
        Deploy the project locally and return a success/failure status.
        """
        project_path = kwargs["project_path"]
        port = kwargs.get("port", 5173)

        # Validate project structure
        if not os.path.exists(os.path.join(project_path, "package.json")):
            return DeployResult(success=False, message="Not a valid project directory (missing package.json)")

        # Change to the project directory
        terminal = Bash()
        await terminal.execute(f"cd {project_path}")

        # Install dependencies if node_modules is missing
        if not os.path.exists(os.path.join(project_path, "node_modules")):
            install_result = await terminal.execute("npm install")
            if install_result.error:
                return DeployResult(
                    success=False,
                    message=f"Failed to install dependencies: {install_result.error}"
                )

        # Start the local development server in background
        command = 'nohup npm run dev -- --port ' + str(port) + ' > /dev/null 2>&1 & echo $!'
        result = await terminal.execute(command)

        # Give some time for server to start
        await asyncio.sleep(2)

        return DeployResult(
            success=True if not result.error else False,
            message=f"Server started on port {port}. Process info: {str(result)}",
            url=f"http://localhost:{port}"
        )
