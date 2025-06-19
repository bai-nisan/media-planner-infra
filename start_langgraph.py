#!/usr/bin/env python3
"""
LangGraph Server Startup Script

This script starts the LangGraph server for local development and Studio integration.
"""

import argparse
import logging
import os
import subprocess
import sys
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def setup_environment():
    """Set up environment variables for LangGraph server."""
    env_vars = {
        "LANGGRAPH_AUTH_TYPE": "noop",
        "LOG_LEVEL": "INFO",
        "POSTGRES_URI": "postgresql://postgres:postgres@localhost:5432/media_planner?sslmode=disable",
        "REDIS_URI": "redis://localhost:6379/0",
        "ENVIRONMENT": "development",
        "DEBUG": "true",
    }

    for key, value in env_vars.items():
        if key not in os.environ:
            os.environ[key] = value
            logger.info(f"Set {key}={value}")


def check_dependencies():
    """Check if required dependencies are installed."""
    try:
        import langgraph
        import langgraph.cli

        logger.info(f"LangGraph version: {langgraph.__version__}")
    except ImportError:
        logger.error("LangGraph not installed. Run: poetry install")
        sys.exit(1)

    # Check if configuration file exists
    config_path = Path("langgraph.json")
    if not config_path.exists():
        logger.error("langgraph.json not found in current directory")
        sys.exit(1)

    logger.info("✅ All dependencies check passed")


def start_server(port=8123, host="0.0.0.0", watch=False, debug=False):
    """Start the LangGraph server."""
    cmd = [
        "python",
        "-m",
        "langgraph",
        "dev",
        "--host",
        host,
        "--port",
        str(port),
        "--config",
        "langgraph.json",
    ]

    if watch:
        cmd.append("--watch")

    if not debug:
        cmd.append("--no-browser")

    logger.info(f"Starting LangGraph server on {host}:{port}")
    logger.info(f"Command: {' '.join(cmd)}")

    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to start LangGraph server: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("Server stopped by user")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Start LangGraph server for media planning"
    )
    parser.add_argument("--port", type=int, default=8123, help="Port to run server on")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--watch", action="store_true", help="Enable file watching")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")

    args = parser.parse_args()

    logger.info("🚀 Starting LangGraph Server for Media Planning")

    # Setup
    setup_environment()
    check_dependencies()

    # Start server
    start_server(port=args.port, host=args.host, watch=args.watch, debug=args.debug)


if __name__ == "__main__":
    main()
