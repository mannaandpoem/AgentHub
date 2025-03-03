from enum import Enum
from typing import Any
import subprocess
import os

from app.tool import BaseTool, Filemap
from app.tool.show_repo_structure import ShowRepoStructureTool


class TemplateType(Enum):
    MINIMAL = "minimal"
    BASIC = "basic"


class CreateWebTemplate(BaseTool):
    name: str = "create_web_template"
    description: str = "Create React project starter templates with predefined directory structures and base configuration"
    parameters: dict = {
        "type": "object",
        "properties": {
            "project_name": {
                "type": "string",
                "description": "Identifier for the template project structure",
                "examples": ["my-react-app"]
            },
            "path": {
                "type": "string",
                "description": "Target directory for template generation",
                "default": ".",
                "examples": ["./projects", "/path/to/workspace"]
            },
            "template_type": {
                "type": "string",
                "enum": ["minimal", "basic"],
                "description": "minimal: Basic setup (src/) | basic: Common project directories (src/, components/, styles/)"
            }
        },
        "required": ["project_name"]
    }

    async def execute(self, **kwargs) -> Any:
        project_name = kwargs.get("project_name")
        path = kwargs.get("path", ".")
        template_type = kwargs.get("template_type", "minimal")

        try:
            # Use create-vite with the minimal template
            create_command = f"yes | npm create vite@latest {project_name} -- --template react"
            subprocess.run(create_command.format(project_name=project_name),
                           shell=True, check=True, cwd=path)

            project_path = os.path.join(path, project_name)
            project_path = os.path.abspath(project_path)

            # Define minimal directory structure
            base_dirs = ["src"]

            if template_type == TemplateType.BASIC.value:
                base_dirs.extend([
                    "src/components",
                    "src/styles",
                    "src/utils",
                    "public"
                ])

            # Create directories
            for dir_path in base_dirs:
                os.makedirs(os.path.join(project_path, dir_path), exist_ok=True)

            # # Install additional dependencies
            # subprocess.run('npm install', shell=True, check=True, cwd=project_path)

            # Show created structure
            show_tool = ShowRepoStructureTool()
            structure = await show_tool.execute(path=project_path)

            filemap_tool = Filemap()
            all_file_map = []
            src_dir = os.path.join(project_path, "src")
            for file in os.listdir(src_dir):
                file_path = os.path.join(src_dir, file)
                if os.path.isdir(file_path):
                    continue

                # Get file content using Filemap
                file_content = await filemap_tool.execute(file_path=file_path)
                all_file_map.append(f"---{file_path}\n{file_content}\n")

            file_map = "\n".join(all_file_map)

            return f"""Template Created: {project_name}
Location: {project_path}

Structure:
{structure}

Filemap of src/:
{file_map}

Template Rules:
1. Main entry point is src/main.jsx - DO NOT MODIFY
2. Global styles in src/index.css - DO NOT MODIFY
3. App logic goes in src/App.jsx - MODIFY THIS
4. Create new components in src/components/
5. Assets go in public/ directory
6. Modify vite.config.js only for advanced configuration

Note: The base template includes essential Vite configuration. 
Maintain the core entry files (main.jsx, App.jsx, index.css) and directory structure for proper compilation.
"""

        except subprocess.CalledProcessError as e:
            return f"❌ Error creating project template: {str(e)}"
