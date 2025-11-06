"""
FastAPI application entrypoint.

This module provides a minimal, extendable FastAPI app with a health endpoint.
Keep this file small and focused to serve as a stable import target for tests.
"""

from fastapi import FastAPI, HTTPException, Query
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware

from src.config.logging import setup_logging
from src.config.settings import settings  # loads environment variables
from src.core.pipeline import run_extraction
from src.models.schema import ExtractionRequest, ExtractionResult, HealthResponse

# Initialize logging on startup
setup_logging()

app = FastAPI(title="PDF Extraction AI", version="0.1.0")

# Configure CORS for frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # Vite dev server (local)
        "http://localhost:3000",  # Alternative frontend port (local)
        "http://localhost:8080",  # Frontend dev server (local)
        "http://pdf-ai-frontend:5173",  # Docker container name
        "http://frontend:5173",  # Docker service name
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", response_model=HealthResponse)
async def health():
    """
    Health endpoint that returns basic service status and environment info.
    """
    return HealthResponse(status="ok", environment=settings.env)


@app.post("/extract", response_model=ExtractionResult)
async def extract(
    request: ExtractionRequest,
    use_cache: bool = Query(True, description="Toggle cache usage for this request."),
):
    """
    Run the full extraction pipeline for a single document.
    """
    try:
        result = await run_in_threadpool(
            run_extraction,
            request,
            use_cache=use_cache,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=500, detail=f"Extraction pipeline error: {exc}"
        ) from exc

    return result
