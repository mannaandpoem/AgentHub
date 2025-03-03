"""
This module monitors the app for shutdown signals
"""

import asyncio
import signal
import sys
import threading
import time
from types import FrameType
from typing import Optional, Callable, List

from uvicorn.server import HANDLED_SIGNALS

from app.logger import logger

_should_exit = None


def _register_signal_handler(sig: signal.Signals):
    original_handler = None

    def handler(sig_: int, frame: FrameType | None):
        logger.debug(f"shutdown_signal:{sig_}")
        global _should_exit
        _should_exit = True
        if original_handler:
            original_handler(sig_, frame)  # type: ignore[unreachable]

    original_handler = signal.signal(sig, handler)


def _register_signal_handlers():
    global _should_exit
    if _should_exit is not None:
        return
    _should_exit = False

    logger.debug("_register_signal_handlers")

    # Check if we're in the main thread of the main interpreter
    if threading.current_thread() is threading.main_thread():
        logger.debug("_register_signal_handlers:main_thread")
        for sig in HANDLED_SIGNALS:
            _register_signal_handler(sig)
    else:
        logger.debug("_register_signal_handlers:not_main_thread")


def should_exit() -> bool:
    _register_signal_handlers()
    return bool(_should_exit)


def should_continue() -> bool:
    _register_signal_handlers()
    return not _should_exit


def sleep_if_should_continue(timeout: float):
    if timeout <= 1:
        time.sleep(timeout)
        return
    start_time = time.time()
    while (time.time() - start_time) < timeout and should_continue():
        time.sleep(1)


async def async_sleep_if_should_continue(timeout: float):
    if timeout <= 1:
        await asyncio.sleep(timeout)
        return
    start_time = time.time()
    while time.time() - start_time < timeout and should_continue():
        await asyncio.sleep(1)


# ----- Shutdown Listener -----
# List to store cleanup handlers
_cleanup_handlers: List[Callable] = []

# Flag to track if shutdown is in progress
_shutdown_in_progress = False

# Store the original event loop
_original_loop: Optional[asyncio.AbstractEventLoop] = None


async def _shutdown():
    """Execute all registered cleanup handlers"""
    global _shutdown_in_progress

    if _shutdown_in_progress:
        logger.warning("Shutdown already in progress")
        return

    _shutdown_in_progress = True
    logger.info("Executing shutdown sequence")

    # Execute all cleanup handlers
    for handler in _cleanup_handlers:
        try:
            if asyncio.iscoroutinefunction(handler):
                await handler()
            else:
                handler()
        except Exception as e:
            logger.error(f"Error in shutdown handler: {e}")

    logger.info("Shutdown complete")


def _signal_handler(sig, frame):
    """Handle termination signals by scheduling the shutdown coroutine"""
    logger.info(f"Received signal {sig}, initiating shutdown")

    try:
        # Get the current event loop
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Schedule the shutdown coroutine
            asyncio.create_task(_shutdown())
        else:
            # If the loop is not running, run the shutdown directly
            loop.run_until_complete(_shutdown())
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")
        sys.exit(1)


def register_shutdown_handler(handler: Optional[Callable] = None):
    """
    Register signal handlers for graceful shutdown.
    Optionally register a cleanup handler function to be called during shutdown.

    Args:
        handler: Optional cleanup function to register
    """
    global _original_loop

    # Store the original event loop for later use
    if _original_loop is None:
        try:
            _original_loop = asyncio.get_event_loop()
        except RuntimeError:
            # Create a new event loop if none exists
            _original_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(_original_loop)

    # Register the cleanup handler if provided
    if handler is not None:
        _cleanup_handlers.append(handler)

    # Register signal handlers if not already done
    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    logger.debug("Registered shutdown handler")

    return handler  # Return the handler for use as a decorator


def add_cleanup_handler(handler: Callable):
    """
    Add a cleanup handler to be called during shutdown.

    Args:
        handler: Cleanup function to register
    """
    _cleanup_handlers.append(handler)
    logger.debug(f"Added cleanup handler: {handler.__name__}")

    return handler  # Return the handler for use as a decorator
