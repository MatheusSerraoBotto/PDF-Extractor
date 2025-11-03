"""
FastAPI application entrypoint.

This module provides a minimal, extendable FastAPI app with a health endpoint.
Keep this file small and focused to serve as a stable import target for tests.
"""

from fastapi import FastAPI
from pydantic import BaseModel

from src.config.settings import settings  # loads environment variables

app = FastAPI(title="PDF Extraction AI", version="0.1.0")


class HealthResponse(BaseModel):
    status: str
    environment: str


@app.get("/health", response_model=HealthResponse)
async def health():
    """
    Health endpoint that returns basic service status and environment info.
    """
    return HealthResponse(status="ok", environment=settings.env)
