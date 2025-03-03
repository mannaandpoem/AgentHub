# main.py
import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

from api import start_server
from app.config import config
from app.utils.shutdown_listener import register_shutdown_handler


# Configure logging based on config
def setup_logging():
    """Configure logging based on config settings"""
    log_level = config.logging.level.upper() if config.logging else "INFO"
    log_file = config.logging.file if config.logging and config.logging.file else "agenthub.log"

    logging.basicConfig(
        level=getattr(logging, log_level),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(log_file)
        ]
    )

    return logging.getLogger("agenthub")


logger = setup_logging()


async def startup():
    """Perform startup tasks"""
    logger.info("Starting AgentHub server...")

    # Register shutdown handler
    register_shutdown_handler()

    # Log configuration details
    if config.api:
        logger.info(f"API Configuration: host={config.api.host}, port={config.api.port}")

    if config.agents:
        logger.info(
            f"Agent Configuration: max_active={config.agents.max_active}, default_type={config.agents.default_type}")

    if config.llm:
        logger.info(f"LLM Configuration: {len(config.llm)} provider(s) configured")
        for name, llm_config in config.llm.items():
            logger.info(f"  - {name}: model={llm_config.model}")

    if config.tools:
        logger.info(f"Tools Configuration: {len(config.tools.allowed)} tools allowed")
        logger.info(f"  - Allowed tools: {', '.join(config.tools.allowed)}")

    logger.info("Startup complete")


def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description="AgentHub Server")
    parser.add_argument("--host", help="Host to bind the server to")
    parser.add_argument("--port", type=int, help="Port to bind the server to")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    parser.add_argument("--config", help="Path to config file")
    parser.add_argument("--log-level",
                        choices=["debug", "info", "warning", "error", "critical"],
                        help="Logging level")
    return parser.parse_args()


def main():
    """Main entry point"""
    args = parse_args()

    # Set config path if provided
    if args.config:
        config_path = Path(args.config)
        if not config_path.exists():
            logger.error(f"Config file not found: {args.config}")
            sys.exit(1)
        os.environ["AGENTHUB_CONFIG_PATH"] = str(config_path)

    # Override config with command line arguments
    if args.host and config.api:
        config.api.host = args.host

    if args.port and config.api:
        config.api.port = args.port

    if args.debug and config.api:
        config.api.debug = args.debug

    if args.log_level and config.logging:
        config.logging.level = args.log_level
        # Reconfigure logging with new level
        setup_logging()

    # Run startup tasks
    asyncio.run(startup())

    # Start the server
    start_server()


if __name__ == "__main__":
    main()
