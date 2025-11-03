"""
Pytest fixtures for integration tests.
Creates an AsyncClient bound to the FastAPI app defined in src.main.
"""

import sys
from pathlib import Path

import pytest_asyncio
from httpx import AsyncClient

# Ensure project root is available for src.* imports when tests run in Docker.
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Import the FastAPI app instance (must be created in src/main.py)
from src.main import app  # noqa: E402


@pytest_asyncio.fixture
async def client():
    """Provide an HTTPX AsyncClient connected to the FastAPI app."""
    async with AsyncClient(app=app, base_url="http://testserver") as ac:
        yield ac
