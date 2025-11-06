"""Simple script to test logging configuration."""

import os
import sys

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from src.config.logging import setup_logging, get_logger


def test_logging_levels():
    """Test different logging levels."""
    levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

    for level in levels:
        print(f"\n{'='*60}")
        print(f"Testing LOG_LEVEL={level}")
        print('='*60)

        # Configure logging with the current level
        os.environ["LOG_LEVEL"] = level

        # Force reload of settings
        from importlib import reload
        from src.config import settings as settings_module
        reload(settings_module)

        # Setup logging
        setup_logging()

        # Get a test logger
        logger = get_logger("test_module")

        # Test all log levels
        logger.debug("This is a DEBUG message")
        logger.info("This is an INFO message")
        logger.warning("This is a WARNING message")
        logger.error("This is an ERROR message")
        logger.critical("This is a CRITICAL message")

        print()


if __name__ == "__main__":
    test_logging_levels()
