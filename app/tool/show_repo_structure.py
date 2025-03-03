from dataclasses import dataclass
from typing import Optional, Dict
import os

from rich.tree import Tree

from app.tool import BaseTool


@dataclass
class RepoStructure:
    path: str  # Project directory path
    files: Dict[str, Optional[Dict]]  # Actual file structure
    explanations: Dict[str, str]  # Directory/file explanations

    def to_string(self) -> str:
        """Convert structure to pretty string representation with simple indentation"""
        root_path = os.path.abspath(self.path)
        project_name = os.path.basename(root_path)
        lines = [f"{project_name} ({root_path})"]

        def build_tree(items: Dict, level: int = 0):
            for name, contents in sorted(items.items()):
                indent = "    " * level
                is_dir = isinstance(contents, dict)

                # Add item with explanation if available
                path = f"{name}/" if is_dir else name
                explanation = self.explanations.get(path.rstrip('/'), '')
                line = f"{indent}{path}"
                if explanation:
                    line += f" → {explanation}"
                lines.append(line)

                # Recurse for directories
                if is_dir and contents:
                    build_tree(contents, level + 1)

        build_tree(self.files)
        return "\n".join(lines)

    def __str__(self):
        return self.to_string()


class ShowRepoStructureTool(BaseTool):
    name: str = "show_repo_structure"
    description: str = "Show the structure of the repository with detailed explanation"
    parameters: dict = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to the project directory"
            }
        },
        "required": ["path"]
    }

    def _create_tree(self, directory: str, tree: Tree) -> None:
        """Recursively create a tree structure."""
        try:
            # Sort directories first, then files
            entries = os.listdir(directory)
            dirs = [e for e in entries if os.path.isdir(os.path.join(directory, e))]
            files = [e for e in entries if os.path.isfile(os.path.join(directory, e))]

            # Sort both lists
            dirs.sort()
            files.sort()

            # Process directories
            for entry in dirs:
                if entry.startswith('.') or entry in ['node_modules', 'dist']:
                    continue
                path = os.path.join(directory, entry)
                branch = tree.add(f"📁 [bold blue]{entry}[/]")
                self._create_tree(path, branch)

            # Process files
            for entry in files:
                if entry.startswith('.'):
                    continue
                tree.add(f"📄 [green]{entry}[/]")

        except Exception as e:
            tree.add(f"[red]Error reading directory: {str(e)}[/]")

    async def execute(self, path: str) -> RepoStructure:
        def scan_directory(directory: str) -> Dict:
            result = {}
            try:
                for entry in sorted(os.listdir(directory)):
                    if entry.startswith('.') or entry in ['node_modules', 'dist']:
                        continue

                    full_path = os.path.join(directory, entry)
                    if os.path.isdir(full_path):
                        result[entry] = scan_directory(full_path)
                    else:
                        result[entry] = None
                return result
            except Exception:
                return {}

        structure = RepoStructure(
            path=path,
            files=scan_directory(path),
            explanations={
                "src": "Source code directory",
                "src/components": "Reusable React components",
                "src/pages": "Page components for routes",
                "src/assets": "Static assets",
                "src/store": "Redux store configuration",
                "public": "Static files served directly",
                "package.json": "Project dependencies and scripts",
                "vite.config.ts": "Vite configuration"
            }
        )

        return structure
