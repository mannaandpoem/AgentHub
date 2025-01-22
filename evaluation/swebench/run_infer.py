import argparse
import asyncio
import json
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List

from app.agent import TaoAgent
from app.agent.code_alchemist import CodeAlchemistAgent
from app.agent.codeact import CodeActAgent
from app.agent.midwit import MidwitAgent
from app.agent.swe import SWEAgent
from app.config import PROJECT_ROOT, WORKSPACE_ROOT, config
from app.logger import logger
from app.tool import Terminal
from evaluation.swebench.utils import load_hf_dataset


INSTANCE_TEMPLATE = f"""
<uploaded_files>
{{working_dir}}
</uploaded_files>
I've uploaded a python code repository in the directory {{working_dir}}. Consider the following PR description:

<pr_description>
{{problem_statement}}
</pr_description>

Can you help me implement the necessary changes to the repository so that the requirements specified in the <pr_description> are met?
I've already taken care of all changes to any of the test files described in the <pr_description>. This means you DON'T have to modify the testing logic or any of the tests in any way!
Your task is to make the minimal changes to non-tests files in the {{working_dir}} directory to ensure the <pr_description> is satisfied.
Follow these steps to resolve the issue:
{{solution_steps}}
"""

SOLUTION_STEPS = """1. As a first step, it might be a good idea to find and read code relevant to the <pr_description>
2. Create a script to reproduce the error and execute it with `python <filename.py>` using the bash tool, to confirm the error
3. Edit the sourcecode of the repo to resolve the issue
4. Rerun your reproduce script and confirm that the error is fixed!
5. Think about edgecases and make sure your fix handles them as well
Your thinking should be thorough and so it's fine if it's very long.
"""

SOLUTION_STEPS_WITHOUT_REPRODUCE = """1. Find and read code relevant to the <pr_description>
2. Edit the sourcecode of the repo to resolve the issue
"""


class DatasetConfig:
    """Configuration for dataset management"""

    MAPPINGS: Dict[str, str] = {
        "lite": "princeton-nlp/SWE-bench_Lite",
        "nano": "manna-ai/SWE-Verified_Nano",
        "mini": "manna-ai/SWE-Verified_Mini",
        "full": "princeton-nlp/SWE-bench_Verified",
    }
    AGENT_MAPPINGS = {
        "swe": SWEAgent,
        "codeact": CodeActAgent,
        "midwit": MidwitAgent,
        "tao": TaoAgent,
        "code_alchemist": CodeAlchemistAgent,
    }
    TEST_REPO_DIR = Path("/Users/manna/data/test_repo")
    DATA_DIR = PROJECT_ROOT / "data/hugging_face"

    @classmethod
    def get_dataset_path(cls) -> str:
        """Get dataset path based on environment variable."""
        data_mode = os.getenv("TYPE", "nano").lower()
        return cls.MAPPINGS.get(data_mode, cls.MAPPINGS["nano"])


class RepositoryManager:
    """Manages git repository operations"""

    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.terminal = Terminal()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.terminal.close()

    def get_repo_path(self, instance: dict) -> Path:
        """Generate repository path from instance information"""
        return self.base_dir / (
            instance["repo"].replace("-", "_").replace("/", "__")
            + "_"
            + instance["version"]
        )

    async def refresh_repo(self, instance: dict, reclone: bool = False) -> Path:
        """Refresh or clone repository based on instance information"""
        repo_path = self.get_repo_path(instance)
        if repo_path.exists() and reclone:
            logger.info(f"Removing existing repo path: {repo_path.absolute()}")
            shutil.rmtree(repo_path)

        if repo_path.exists():
            await self._handle_existing_repo(repo_path)
        else:
            await self._clone_new_repo(
                repo_path, instance["repo"], instance["base_commit"]
            )

        logger.info(await self.terminal.execute(f"pwd"))
        return repo_path

    async def _handle_existing_repo(self, repo_path: Path):
        """Handle operations for existing repository"""
        logger.info(f"Resetting existing repo path: {repo_path.absolute()}")
        commands = [
            f"cd {repo_path.absolute()}",
            "git reset --hard && git clean -n -d && git clean -f -d",
            "git rev-parse --abbrev-ref HEAD | xargs git checkout",
            "git branch",
            "pwd",
        ]
        for cmd in commands:
            await self._run_command(cmd)

    async def _clone_new_repo(
        self, repo_path: Path, repo_identifier: str, base_commit: str
    ):
        """Clone a new repository"""
        logger.info(f"Cloning repo to path: {repo_path}")
        commands = [
            f"git clone 'https://github.com/{repo_identifier}.git' {repo_path.absolute()}",
            f"cd {repo_path.absolute()}"
            + (f" && git checkout -f {base_commit}" if base_commit else ""),
            "git branch",
            "pwd",
        ]
        for cmd in commands:
            await self._run_command(cmd)

    async def get_git_diff(self, repo_path: Path) -> str:
        """Get git diff for modified files"""
        commands = [
            f"cd {repo_path.absolute()} ",
            "echo '.backup.*' >> .gitignore",
            "git add -A",
            "git diff --cached",
        ]
        output = ""
        for cmd in commands:
            output = await self._run_command(cmd)
        return output

    async def _run_command(self, cmd: str) -> str:
        """Execute a command in terminal and return output"""
        output = await self.terminal.execute(cmd)
        logger.info(f"Command: {cmd}\nOutput:\n{output}")
        return str(output)


class BenchmarkRunner:
    """Main class for running the SWE benchmark"""

    def __init__(self, args: argparse.Namespace):
        self.args = args
        self.result_dir = Path(args.save_folder)
        self.repo_manager = RepositoryManager(Path(args.test_repo_dir))

    async def run(self):
        """Main execution flow"""
        dataset = self._load_dataset()
        self.result_dir.mkdir(parents=True, exist_ok=True)

        async with self.repo_manager:
            for index, instance in enumerate(dataset):
                await self._run_instance(index, instance)

    def _load_dataset(self):
        """Load and filter dataset based on instance IDs"""
        dataset_path = DatasetConfig.get_dataset_path()
        dataset = self._load_hf_dataset(dataset_path)

        # Get instance IDs from args or fallback to default
        instance_ids = self.args.instance_ids
        if instance_ids is None:
            # Default hardcoded or environment variable
            instance_ids = ["django__django-13820"]
            instance_ids = ["astropy__astropy-14309"]
        elif instance_ids == ["all"]:
            # Select all instances
            logger.info("Using all available instances")
            return dataset

        # Filter dataset by instance IDs
        logger.info(f"Filtering dataset for instance IDs: {instance_ids}")
        return self._filter_dataset(dataset, instance_ids)

    @staticmethod
    def _load_hf_dataset(dataset_path: str):
        """Load dataset from Hugging Face"""

        return load_hf_dataset(
            dataset_name_or_path=dataset_path,
            cache_dir=DatasetConfig.DATA_DIR,
            split="test",
        )

    @staticmethod
    def _filter_dataset(dataset, instance_ids: List[str]):
        """Filter dataset based on instance IDs"""
        instance_ids = [id.strip() for id in instance_ids]
        return dataset.filter(
            lambda x: x["instance_id"] in instance_ids,
            desc="Filtering out existing ids",
            load_from_cache_file=True,
        )

    async def _run_instance(self, index: int, instance: dict):
        """Run a single instance of the benchmark"""
        if not self._should_run_instance(instance):
            logger.info(f"Instance {instance['instance_id']} already exists, skipping")
            return

        self._setup_logging(index, instance)
        await self._execute_instance(instance)

    def _should_run_instance(self, instance: dict) -> bool:
        """Check if instance should be run"""
        output_file = self.result_dir / "all_preds.jsonl"
        if not output_file.exists():
            return True

        with open(output_file, "r") as fp:
            return not any(
                json.loads(line.strip())["instance_id"] == instance["instance_id"]
                for line in fp
            )

    def _setup_logging(self, index: int, instance: dict):
        """Setup logging for instance"""
        logger.remove()
        logger.add(sys.stderr, level="INFO")
        logger.add(
            self.result_dir / "logs" / f"{index + 1}_{instance['instance_id']}.log",
            level="DEBUG",
        )

    async def _execute_instance(self, instance: dict):
        """Execute instance and save results"""
        logger.info(f"**** Preparing to run {instance['instance_id']} ****")
        repo_path = await self.repo_manager.refresh_repo(
            instance, self.args.reclone_existing_repo
        )

        agent = DatasetConfig.AGENT_MAPPINGS[self.args.agent](
            max_steps=self.args.max_steps
        )
        env_name = await self.get_env_name(instance)
        if not hasattr(agent, "env_name") or not agent.env_name:
            setattr(agent, "env_name", env_name)
        user_requirement = self._prepare_requirement(instance, repo_path)

        logger.info(f"**** Starting to run {instance['instance_id']} ****")
        logger.info("User Requirement:\n" + user_requirement)

        await agent.run(user_requirement)
        logger.info(f"**** Finished running {instance['instance_id']} ****")

        instance["model_name_or_path"] = agent.llm.model

        repo_path = self.repo_manager.get_repo_path(instance)
        instance["model_patch"] = await self.generate_patch(repo_path)
        logger.info(f"Model patch:\n{instance['model_patch']}")

        await self._save_predictions(instance)

    @staticmethod
    async def get_env_name(instance):
        repo = instance["repo"]
        env_name = ""
        if not env_name:
            repo_prefix = repo.replace("/", "__").replace("-", "_")
            version = instance["version"]
            env_name = f"{repo_prefix}_{version}"

        return env_name

    @staticmethod
    def _prepare_requirement(instance: dict, repo_path: Path) -> str:
        """Prepare user requirement text"""
        return INSTANCE_TEMPLATE.format(
            problem_statement=instance["problem_statement"],
            hints_text=instance["hints_text"],
            working_dir=repo_path.absolute(),
            solution_steps=SOLUTION_STEPS
            if args.reproduce
            else SOLUTION_STEPS_WITHOUT_REPRODUCE,
        )

    async def generate_patch(self, repo_path: Path) -> str:
        """Generate git diff patch for the repository"""
        return await self.repo_manager.get_git_diff(repo_path)

    async def _save_predictions(self, instance: dict):
        """Save predictions to output file"""
        output_file = self.result_dir / "all_preds.jsonl"
        logger.info(f"Saving predictions to {output_file}")

        with open(output_file, "a+") as fp:
            print(json.dumps(instance), file=fp, flush=True)

        logger.info(f"Saved prediction of {instance['instance_id']}")


def parse_args() -> argparse.Namespace:
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description="SWE Benchmark Runner")
    llm_config = config.llm["default"]  # Fixme: Use a specific model
    default_result_dir = (
        WORKSPACE_ROOT
        / f"result_{llm_config.model.replace('/', '_')}_{datetime.now().strftime('%Y_%m_%d_%H_%M')}"
    )

    parser.add_argument(
        "-rw",
        "--test_repo_dir",
        default=DatasetConfig.TEST_REPO_DIR.absolute(),
        help="Directory to save temporary repositories",
        type=str,
    )
    parser.add_argument(
        "-s",
        "--save_folder",
        default=default_result_dir,
        help="Folder to save results and logs",
        type=str,
    )
    parser.add_argument(
        "-o",
        "--reclone_existing_repo",
        action="store_true",
        help="If set, existing repository will be removed and recloned",
    )
    parser.add_argument(
        "-a",
        "--agent",
        choices=["swe", "codeact", "midwit", "tao"],
        default="tao",
        help="Select the agent: swe_agent, swe_agent2, or codeact_agent.",
    )
    parser.add_argument(
        "-r",
        "--reproduce",
        action="store_true",
        help="If set, the agent will be asked to reproduce the error before fixing it.",
    )
    parser.add_argument(
        "-m",
        "--max_steps",
        default=30,
        type=int,
        help="Maximum number of steps to run the agent",
    )
    parser.add_argument(
        "--instance_ids",
        nargs="+",
        help="Specify one or more instance IDs (e.g., 'django__django-13820'). Use 'all' to select all instances.",
    )

    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    runner = BenchmarkRunner(args)
    asyncio.run(runner.run())
